import hashlib
import json
from datetime import date, time, timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from usuarios.models import Usuario

from .models import Clase, ClaseAlumno, ClaseProfesor, Feriado, TurnoPlanilla
from .permisos import exigir_administracion_clases
from .servicios import bloquear_calendario_clases, bloquear_usuarios_clase
from .validaciones import validar_periodo_generacion, validar_usuarios_clase


def _fechas_del_periodo(fecha_desde, fecha_hasta):
    return [fecha_desde + timedelta(days=numero) for numero in range((fecha_hasta - fecha_desde).days + 1)]


def _revisar_generacion(sede_id, fecha_desde, fecha_hasta):
    sede = Sede.objects.get(pk=sede_id)
    canchas = list(Cancha.objects.filter(sede=sede).order_by("pk"))
    celdas = list(TurnoPlanilla.objects.filter(cancha__sede=sede).select_related("cancha").prefetch_related(
        "profesores", "alumnos",
    ).order_by("hora_inicio", "cancha_id", "pk"))
    usuarios_ids = set()
    for celda in celdas:
        usuarios_ids.update(v.profesor_id for v in celda.profesores.all())
        usuarios_ids.update(v.usuario_id for v in celda.alumnos.all())
    usuarios = {
        usuario.pk: usuario
        for usuario in Usuario.objects.filter(pk__in=usuarios_ids).prefetch_related("roles__rol")
    }
    horarios = {
        horario.dia_semana: [
            [horario.hora_inicio_1, horario.hora_fin_1],
            *([[horario.hora_inicio_2, horario.hora_fin_2]] if horario.hora_inicio_2 is not None else []),
        ]
        for horario in sede.horarios.all()
    }
    feriados = set(Feriado.objects.filter(fecha__range=(fecha_desde, fecha_hasta)).values_list("fecha", flat=True))
    eventos = list(Evento.objects.filter(
        turno__cancha__sede=sede, turno__fecha__range=(fecha_desde, fecha_hasta),
    ).exclude(estado=Evento.Estado.ANULADO).values_list(
        "pk", "tipo", "estado", "actualizado_en", "turno__cancha_id", "turno__fecha", "turno__hora_inicio",
    ).order_by("pk"))
    ocupados = {(evento[4], evento[5], evento[6]) for evento in eventos}
    filtros_asignacion = {
        "estado": "activo",
        "clase__evento__turno__fecha__range": (fecha_desde, fecha_hasta),
    }
    profesores_ocupados = list(ClaseProfesor.objects.filter(
        profesor_id__in=usuarios_ids, **filtros_asignacion,
    ).exclude(clase__evento__estado=Evento.Estado.ANULADO).values_list(
        "clase_id", "profesor_id", "clase__evento__turno__fecha", "clase__evento__turno__hora_inicio",
    ).order_by("clase_id", "profesor_id"))
    participantes_ocupados = list(ClaseAlumno.objects.filter(
        usuario_id__in=usuarios_ids, **filtros_asignacion,
    ).exclude(clase__evento__estado=Evento.Estado.ANULADO).values_list(
        "clase_id", "usuario_id", "clase__evento__turno__fecha", "clase__evento__turno__hora_inicio",
    ).order_by("clase_id", "usuario_id"))
    asignaciones_ocupadas = {
        (fecha, hora, usuario_id)
        for _, usuario_id, fecha, hora in profesores_ocupados + participantes_ocupados
    }
    candidatas = []
    omitidas = []
    planilla = []
    for celda in celdas:
        profesores_ids = sorted(v.profesor_id for v in celda.profesores.all())
        participantes_ids = sorted(v.usuario_id for v in celda.alumnos.all())
        motivo_usuarios = ""
        try:
            validar_usuarios_clase(usuarios, set(profesores_ids), set(participantes_ids))
        except ValidationError as error:
            motivo_usuarios = "; ".join(error.messages)
        planilla.append([
            celda.pk, celda.cancha_id, celda.dia_semana, celda.hora_inicio, celda.modalidad,
            celda.observaciones, celda.actualizado_en, profesores_ids, participantes_ids,
        ])
        for fecha in _fechas_del_periodo(fecha_desde, fecha_hasta):
            if fecha.isoweekday() == celda.dia_semana:
                candidatas.append({
                    "turno_planilla_id": celda.pk, "cancha_id": celda.cancha_id,
                    "fecha": fecha, "hora_inicio": celda.hora_inicio,
                    "modalidad": celda.modalidad, "observaciones": celda.observaciones or "",
                    "profesores_ids": profesores_ids, "participantes_ids": participantes_ids,
                    "motivo_usuarios": motivo_usuarios, "cancha_activa": celda.cancha.estado == Cancha.Estado.ACTIVA,
                })
    candidatas.sort(key=lambda candidata: (
        candidata["fecha"], candidata["hora_inicio"], sede.pk, candidata["cancha_id"],
    ))
    validas = []
    for candidata in candidatas:
        fecha = candidata["fecha"]
        hora = candidata["hora_inicio"]
        participantes = set(candidata["profesores_ids"]) | set(candidata["participantes_ids"])
        motivo = ""
        if fecha in feriados:
            motivo = "Feriado."
        elif sede.estado != Sede.Estado.ACTIVA or not candidata["cancha_activa"]:
            motivo = "La sede o la cancha están inactivas."
        elif candidata["motivo_usuarios"]:
            motivo = candidata["motivo_usuarios"]
        elif not any(hora >= inicio and time(hora.hour + 1) <= fin for inicio, fin in horarios.get(fecha.isoweekday(), [])):
            motivo = "El turno está fuera del horario de funcionamiento."
        elif (candidata["cancha_id"], fecha, hora) in ocupados:
            motivo = "El turno está ocupado por una actividad no Anulada."
        elif any((fecha, hora, usuario_id) in asignaciones_ocupadas for usuario_id in participantes):
            motivo = "Un profesor o participante tiene otra clase asignada en esa fecha y hora."
        candidata.pop("motivo_usuarios")
        candidata.pop("cancha_activa")
        if motivo:
            omitidas.append({**candidata, "motivo": motivo})
        else:
            validas.append(candidata)
            asignaciones_ocupadas.update((fecha, hora, usuario_id) for usuario_id in participantes)
    instantanea = {
        "sede": [sede.pk, sede.nombre, sede.estado],
        "canchas": [[cancha.pk, cancha.nombre, cancha.estado] for cancha in canchas],
        "desde": fecha_desde, "hasta": fecha_hasta, "planilla": planilla, "horarios": horarios,
        "feriados": sorted(feriados), "eventos": eventos,
        "docencia_ocupada": profesores_ocupados, "participacion_ocupada": participantes_ocupados,
        "usuarios": [
            [usuario.pk, str(usuario), usuario.is_active, sorted(v.rol.codigo for v in usuario.roles.all())]
            for usuario in sorted(usuarios.values(), key=lambda usuario: usuario.pk)
        ],
        "validas": validas, "omitidas": omitidas,
    }
    huella = hashlib.sha256(json.dumps(instantanea, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "sede_id": sede.pk, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
        "candidatas": validas, "omitidas": omitidas, "usuarios_ids": sorted(usuarios_ids), "huella": huella,
        "irreversible": True, "confirmaciones_requeridas": 2,
    }


def _firmar_revision(usuario, revision, etapa):
    return signing.dumps({
        "usuario": usuario.pk, "sede": revision["sede_id"],
        "desde": revision["fecha_desde"].isoformat(), "hasta": revision["fecha_hasta"].isoformat(),
        "huella": revision["huella"], "etapa": etapa,
    }, salt="clases.generacion", compress=True)


def _leer_revision(usuario, confirmacion, etapa):
    try:
        datos = signing.loads(confirmacion, salt="clases.generacion")
        if datos["usuario"] != usuario.pk or datos["etapa"] != etapa:
            raise signing.BadSignature
        fecha_desde = date.fromisoformat(datos["desde"])
        fecha_hasta = date.fromisoformat(datos["hasta"])
        validar_periodo_generacion(fecha_desde, fecha_hasta)
        revision = _revisar_generacion(datos["sede"], fecha_desde, fecha_hasta)
        if revision["huella"] != datos["huella"]:
            raise ValidationError("La programación o la ocupación cambió. Revisá nuevamente la generación.")
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError("La confirmación no corresponde a esta etapa o usuario. Revisá la generación.") from None
    return revision


def preparar_generacion(usuario, sede_id, fecha_desde, fecha_hasta):
    usuario = exigir_administracion_clases(usuario)
    validar_periodo_generacion(fecha_desde, fecha_hasta)
    revision = _revisar_generacion(sede_id, fecha_desde, fecha_hasta)
    revision["confirmacion"] = _firmar_revision(usuario, revision, "revision")
    return revision


def confirmar_generacion(usuario, confirmacion):
    usuario = exigir_administracion_clases(usuario)
    revision = _leer_revision(usuario, confirmacion, "revision")
    revision["confirmacion"] = _firmar_revision(usuario, revision, "primera_confirmacion")
    return revision


def _crear_clases_generadas(usuario, candidatas, turnos):
    nuevos = [
        Turno(cancha_id=fila["cancha_id"], fecha=fila["fecha"], hora_inicio=fila["hora_inicio"])
        for fila in candidatas if (fila["cancha_id"], fila["fecha"], fila["hora_inicio"]) not in turnos
    ]
    Turno.objects.bulk_create(nuevos, batch_size=500)
    turnos.update({(turno.cancha_id, turno.fecha, turno.hora_inicio): turno for turno in nuevos})
    eventos = [
        Evento(
            turno=turnos[(fila["cancha_id"], fila["fecha"], fila["hora_inicio"])],
            tipo=Evento.Tipo.CLASE, registrado_por=usuario, observaciones=fila["observaciones"],
        )
        for fila in candidatas
    ]
    Evento.objects.bulk_create(eventos, batch_size=500)
    clases = [
        Clase(evento=evento, turno_planilla_id=fila["turno_planilla_id"], es_generada=True, modalidad=fila["modalidad"])
        for fila, evento in zip(candidatas, eventos)
    ]
    Clase.objects.bulk_create(clases, batch_size=500)
    ClaseProfesor.objects.bulk_create([
        ClaseProfesor(clase=clase, profesor_id=usuario_id)
        for fila, clase in zip(candidatas, clases) for usuario_id in fila["profesores_ids"]
    ], batch_size=500)
    ClaseAlumno.objects.bulk_create([
        ClaseAlumno(clase=clase, usuario_id=usuario_id)
        for fila, clase in zip(candidatas, clases) for usuario_id in fila["participantes_ids"]
    ], batch_size=500)
    return clases


@transaction.atomic
def generar_clases(usuario, confirmacion):
    usuario = exigir_administracion_clases(usuario)
    seleccion = _leer_revision(usuario, confirmacion, "primera_confirmacion")
    usuarios = bloquear_usuarios_clase(set(seleccion["usuarios_ids"]) | {usuario.pk})
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    for fecha in _fechas_del_periodo(seleccion["fecha_desde"], seleccion["fecha_hasta"]):
        bloquear_calendario_clases(fecha)
    sede = Sede.objects.select_for_update().get(pk=seleccion["sede_id"])
    list(Cancha.objects.select_for_update().filter(sede=sede).order_by("pk"))
    list(TurnoPlanilla.objects.select_for_update(of=("self",)).filter(cancha__sede=sede).order_by("pk"))
    turnos = list(Turno.objects.select_for_update(of=("self",)).filter(
        cancha__sede=sede, fecha__range=(seleccion["fecha_desde"], seleccion["fecha_hasta"]),
    ).order_by("pk"))
    list(Evento.objects.select_for_update().filter(turno__in=turnos).order_by("pk"))
    revision = _revisar_generacion(sede.pk, seleccion["fecha_desde"], seleccion["fecha_hasta"])
    if revision["huella"] != seleccion["huella"]:
        raise ValidationError("La programación o la ocupación cambió. Revisá nuevamente la generación.")
    turnos_por_coordenadas = {(turno.cancha_id, turno.fecha, turno.hora_inicio): turno for turno in turnos}
    clases = _crear_clases_generadas(usuario, revision["candidatas"], turnos_por_coordenadas)
    return {"clases_creadas": len(clases), "clases_ids": [clase.pk for clase in clases], "omitidas": revision["omitidas"]}
