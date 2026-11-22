import hashlib
import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from bloqueos.models import Bloqueo
from bloqueos.servicios import anular_bloqueo, registrar_bloqueo, validar_anulacion_bloqueo
from clases.permisos import exigir_administracion_clases
from clases.servicios import anular_clase, bloquear_usuarios_clase
from clases.validaciones import validar_anulacion_clase
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda, fecha_maxima_eventos
from instalaciones.horarios import horario_efectivo, horarios_del_mes
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from reservas.servicios import anular_reserva, validar_anulacion_reserva


def _preparar_operacion_dia(sede, canchas, fecha, parametros, franjas, ahora, ocupacion):
    operacion = parametros["operacion"]
    actividades = parametros["actividades"]
    corte = time.fromisoformat(parametros["hora_desde"]) if parametros["alcance"] == "desde" else time.min
    hasta = time.fromisoformat(parametros["hora_hasta"]) if parametros["hora_hasta"] else None
    horas_habilitadas = {
        hora for hora in range(23)
        if time(hora) >= corte and (hasta is None or time(hora + 1) <= hasta)
        and any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
    }
    filas = []
    for cancha in canchas:
        eventos = ocupacion.get(cancha.pk, {})
        horas = horas_habilitadas | eventos.keys()
        for hora in sorted(horas):
            inicio = timezone.make_aware(datetime.combine(fecha, time(hora)))
            evento = eventos.get(hora)
            fila = {
                "cancha": cancha, "fecha": fecha, "hora": time(hora), "fin": time(hora + 1),
                "evento": evento, "accion": "", "conservado": "",
                "actividad": "Turno libre", "identificador": "", "reserva": None, "bloqueo": None, "clase": None,
            }
            if evento:
                fila["actividad"] = evento.get_tipo_display()
                if evento.tipo == Evento.Tipo.RESERVA:
                    fila["reserva"] = evento.reserva
                    fila["identificador"] = evento.reserva.numero
                elif evento.tipo == Evento.Tipo.CLASE:
                    fila["clase"] = evento.clase
                    fila["identificador"] = str(evento.clase)
                elif evento.tipo == Evento.Tipo.BLOQUEO:
                    fila["bloqueo"] = evento.bloqueo
                    fila["identificador"] = evento.bloqueo.numero
            if evento and evento.estado == Evento.Estado.FINALIZADO:
                fila["conservado"] = "Finalizado"
            elif inicio <= ahora:
                fila["conservado"] = "En curso" if inicio + timedelta(hours=1) > ahora else "Terminado"
            elif fila["clase"] and (
                "clase_generada" if fila["clase"].es_generada else "clase_manual"
            ) not in actividades:
                fila["conservado"] = "Clase fuera de la selección"
            elif fila["reserva"] and "reserva" not in actividades:
                fila["conservado"] = "Reserva fuera de la selección"
            elif evento and evento.tipo == Evento.Tipo.BLOQUEO and operacion == "bloquear":
                fila["conservado"] = "Bloqueo existente"
            elif fila["bloqueo"] and "bloqueo" not in actividades:
                fila["conservado"] = "Bloqueo fuera de la selección"
            elif operacion == "bloquear" and hora not in horas_habilitadas:
                fila["conservado"] = "Fuera del horario vigente"
            elif operacion == "bloquear":
                if fila["reserva"]:
                    validar_anulacion_reserva(fila["reserva"], True, ahora)
                elif fila["clase"]:
                    validar_anulacion_clase(fila["clase"], ahora)
                fila["accion"] = "Anular y bloquear" if evento else "Crear bloqueo"
            elif fila["reserva"]:
                validar_anulacion_reserva(fila["reserva"], True, ahora)
                fila["accion"] = "Anular y liberar"
            elif fila["clase"]:
                validar_anulacion_clase(fila["clase"], ahora)
                fila["accion"] = "Anular y liberar"
            elif fila["bloqueo"]:
                validar_anulacion_bloqueo(fila["bloqueo"], ahora)
                fila["accion"] = "Anular y liberar"
            filas.append(fila)

    acciones = [fila for fila in filas if fila["accion"]]
    conservados = [fila for fila in filas if fila["evento"] and fila["conservado"]]
    reservas_a_anular = sum(fila["reserva"] is not None for fila in acciones)
    anulaciones = sum(fila["evento"] is not None for fila in acciones)
    instantanea = {
        "sede": [sede.pk, sede.nombre, sede.estado],
        "fecha": fecha.isoformat(),
        "canchas": [[cancha.pk, cancha.nombre, cancha.estado] for cancha in canchas],
        "franjas": [[inicio.isoformat(), fin.isoformat()] for inicio, fin in franjas],
        "clases": [
            {
                "id": fila["clase"].pk,
                "profesores": sorted([
                    [vinculo.profesor_id, str(vinculo.identidad), vinculo.actualizado_en.isoformat()]
                    for vinculo in fila["clase"].profesores.all()
                ]),
                "participantes": sorted([
                    [vinculo.usuario_id, str(vinculo.identidad), vinculo.actualizado_en.isoformat()]
                    for vinculo in fila["clase"].alumnos.all()
                ]),
            }
            for fila in filas if fila["clase"] is not None
        ],
        "invitados": [
            sorted(
                (invitado.usuario_id, invitado.respuesta, invitado.actualizado_en)
                for invitado in fila["reserva"].invitados.all()
            )
            for fila in filas if fila["reserva"]
        ],
        "filas": [
            [fila["cancha"].pk, fila["hora"].isoformat(), fila["accion"], fila["conservado"],
             fila["evento"].pk if fila["evento"] else None,
             fila["evento"].estado if fila["evento"] else None,
             fila["evento"].actualizado_en.isoformat() if fila["evento"] else None]
            for fila in filas
        ],
    }
    huella = hashlib.sha256(json.dumps(instantanea, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "acciones": acciones, "conservados": conservados, "canchas": canchas,
        "fechas": [fecha],
        "anulaciones": anulaciones, "reservas_a_anular": reservas_a_anular,
        "clases_a_anular": sum(fila["clase"] is not None for fila in acciones),
        "bloqueos_a_crear": len(acciones) if operacion == "bloquear" else 0,
        "libres_sin_accion": sum(not fila["evento"] and not fila["accion"] for fila in filas),
        "huella": huella,
    }


def _fechas_operacion(fecha, fecha_hasta, parametros, hoy):
    if fecha_hasta is None:
        if not hoy <= fecha <= fecha_maxima_agenda():
            raise ValidationError("Elegí una fecha desde hoy hasta un año después, inclusive.")
        return [fecha], fecha, fecha
    if parametros["operacion"] != "liberar":
        raise ValidationError("Las acciones del mes sólo permiten anular y liberar.")
    if (
        fecha.day != 1 or fecha_hasta != fecha.replace(day=monthrange(fecha.year, fecha.month)[1])
        or fecha < max(FECHA_INICIO_OPERACIONES, hoy.replace(day=1))
        or fecha_hasta > fecha_maxima_eventos()
    ):
        raise ValidationError("Elegí un mes completo dentro del calendario operativo.")
    primera_fecha = max(fecha, hoy)
    try:
        desde = date.fromisoformat(parametros["fecha_desde"]) if "fecha_desde" in parametros else primera_fecha
        hasta = date.fromisoformat(parametros["fecha_hasta"]) if "fecha_hasta" in parametros else fecha_hasta
        dias_semana = set(parametros.get("dias_semana", ()))
    except (TypeError, ValueError):
        raise ValidationError("Revisá las fechas y los días de la semana.") from None
    if not primera_fecha <= desde <= hasta <= fecha_hasta:
        raise ValidationError("Elegí un rango válido dentro del mes, desde hoy en adelante.")
    if not dias_semana <= set(range(1, 8)):
        raise ValidationError("Revisá los días de la semana elegidos.")
    dias_del_rango = (desde + timedelta(days=numero) for numero in range((hasta - desde).days + 1))
    fechas = [dia for dia in dias_del_rango if not dias_semana or dia.isoweekday() in dias_semana]
    if not fechas:
        raise ValidationError("Ninguno de los días de la semana elegidos cae dentro del rango.")
    return fechas, desde, hasta


def preparar_operacion(fecha, parametros, fecha_hasta=None):
    operacion = parametros["operacion"]
    if operacion not in ("liberar", "bloquear"):
        raise ValidationError("Elegí una operación válida.")
    if operacion == "liberar" and not parametros["actividades"]:
        raise ValidationError("Elegí al menos un tipo de actividad.")
    if operacion == "bloquear":
        maxima = fecha_maxima_eventos()
        if fecha > maxima:
            raise ValidationError(f"Sólo se pueden crear bloqueos hasta el {maxima:%d/%m/%Y}, inclusive.")
        if parametros["motivo_bloqueo"] not in Bloqueo.Motivo.values:
            raise ValidationError("Elegí un motivo de bloqueo válido.")

    ahora = timezone.localtime()
    fechas, desde, hasta = _fechas_operacion(fecha, fecha_hasta, parametros, ahora.date())
    sedes = Sede.objects.order_by("pk")
    if parametros["seleccion_sedes"] == "seleccionar":
        sedes = sedes.filter(pk__in=parametros["sedes"])
    sedes = list(sedes)
    if not sedes or [sede.pk for sede in sedes] != parametros["sedes"]:
        raise ValidationError("El alcance de sedes cambió. Revisá nuevamente la selección.")

    canchas = Cancha.objects.filter(sede__in=sedes).select_related("sede").order_by("pk")
    if parametros["seleccion_canchas"] == "seleccionar":
        canchas = canchas.filter(pk__in=parametros["canchas"])
    canchas = list(canchas)
    if not canchas or [cancha.pk for cancha in canchas] != parametros["canchas"]:
        raise ValidationError("El alcance de canchas cambió. Revisá nuevamente la selección.")
    if operacion == "bloquear" and (
        any(sede.estado != Sede.Estado.ACTIVA for sede in sedes)
        or any(cancha.estado != Cancha.Estado.ACTIVA for cancha in canchas)
    ):
        raise ValidationError("Para bloquear, elegí únicamente sedes y canchas activas.")

    horarios = {
        sede.pk: horarios_del_mes(sede, fecha) if fecha_hasta else {fecha: horario_efectivo(sede, fecha)}
        for sede in sedes
    }
    if parametros["hora_hasta"]:
        inicio_elegido = time.fromisoformat(parametros["hora_desde"] or "00:00")
        fin_elegido = time.fromisoformat(parametros["hora_hasta"])
        if (
            parametros["alcance"] != "desde" or fin_elegido <= inicio_elegido
            or fin_elegido.minute or fin_elegido.second or fin_elegido.microsecond
            or not any(
                inicio < fin_elegido <= fin
                for dias in horarios.values() for horario in dias.values() for inicio, fin in horario.franjas
            )
        ):
            raise ValidationError("La hora de fin debe ser posterior al inicio y coincidir con el fin de un turno habilitado.")

    canchas_por_sede = {sede.pk: [] for sede in sedes}
    for cancha in canchas:
        canchas_por_sede[cancha.sede_id].append(cancha)
    corte = time.fromisoformat(parametros["hora_desde"]) if parametros["alcance"] == "desde" else time.min
    eventos = Evento.objects.filter(
        turno__cancha__in=canchas, turno__fecha__in=fechas, turno__hora_inicio__gte=corte,
    ).exclude(estado=Evento.Estado.ANULADO).select_related("turno", "reserva__organizador", "bloqueo", "clase").prefetch_related(
        "clase__profesores", "clase__alumnos", "reserva__invitados",
    )
    if parametros["hora_hasta"]:
        eventos = eventos.filter(turno__hora_inicio__lt=fin_elegido)
    ocupacion_por_fecha = defaultdict(lambda: defaultdict(dict))
    for evento in eventos:
        turno = evento.turno
        ocupacion_por_fecha[turno.fecha][turno.cancha_id][turno.hora_inicio.hour] = evento

    dias = [
        _preparar_operacion_dia(
            sede, canchas_por_sede[sede.pk], dia, parametros, horarios[sede.pk][dia].franjas,
            ahora, ocupacion_por_fecha[dia],
        )
        for dia in fechas for sede in sedes if canchas_por_sede[sede.pk]
    ]
    return {
        "acciones": [fila for dia in dias for fila in dia["acciones"]],
        "conservados": [fila for dia in dias for fila in dia["conservados"]],
        "sedes": sedes, "canchas": canchas,
        "fechas": fechas,
        "desde": desde, "hasta": hasta,
        **{
            campo: sum(dia[campo] for dia in dias)
            for campo in ("anulaciones", "reservas_a_anular", "clases_a_anular", "bloqueos_a_crear", "libres_sin_accion")
        },
        "huella": hashlib.sha256(json.dumps({
            "sedes": [[sede.pk, sede.nombre, sede.estado] for sede in sedes],
            "dias": [dia["huella"] for dia in dias],
        }, sort_keys=True).encode()).hexdigest(),
    }


@transaction.atomic
def ejecutar_operacion(usuario, fecha, parametros, huella, fecha_hasta=None):
    usuario = exigir_administracion_clases(usuario)
    seleccion = preparar_operacion(fecha, parametros, fecha_hasta)
    if seleccion["huella"] != huella:
        raise ValidationError("La agenda o el horario cambió desde la vista previa. Revisá nuevamente las acciones.")
    usuarios_ids = {usuario.pk}
    for fila in seleccion["acciones"]:
        if fila["clase"] is not None:
            usuarios_ids.update(vinculo.profesor_id for vinculo in fila["clase"].profesores.all())
            usuarios_ids.update(vinculo.usuario_id for vinculo in fila["clase"].alumnos.all())
    for fila in seleccion["acciones"]:
        if fila["reserva"] is not None:
            usuarios_ids.add(fila["reserva"].organizador_id)
            usuarios_ids.update(invitado.usuario_id for invitado in fila["reserva"].invitados.all())
    usuarios = bloquear_usuarios_clase(usuarios_ids)
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    list(Sede.objects.select_for_update().filter(pk__in=parametros["sedes"]).order_by("pk"))
    list(Cancha.objects.select_for_update().filter(pk__in=parametros["canchas"]).order_by("pk"))
    # Todos los turnos se bloquean antes de los eventos, igual que en las acciones individuales.
    turnos = list(Turno.objects.select_for_update().filter(
        cancha_id__in=parametros["canchas"], fecha__in=seleccion["fechas"],
    ).order_by("pk"))
    list(Evento.objects.select_for_update().filter(turno__in=turnos).order_by("pk"))
    previa = preparar_operacion(fecha, parametros, fecha_hasta)
    if previa["huella"] != huella:
        raise ValidationError("La agenda o el horario cambió desde la vista previa. Revisá nuevamente las acciones.")
    if not previa["acciones"]:
        raise ValidationError("No hay acciones para confirmar con este alcance.")
    bloquear = parametros["operacion"] == "bloquear"
    motivo = Bloqueo.Motivo(parametros["motivo_bloqueo"]).label if bloquear else parametros["motivo_anulacion"].strip()
    if previa["anulaciones"] and not motivo:
        raise ValidationError("Indicá el motivo de la anulación.")
    if previa["anulaciones"] and len(motivo) < 5:
        raise ValidationError("El motivo de anulación debe tener al menos 5 caracteres.")

    with contexto_auditoria(usuario):
        for fila in previa["acciones"]:
            if parametros["operacion"] == "bloquear":
                registrar_bloqueo(
                    usuario, fila["cancha"], fila["fecha"], fila["hora"], parametros["motivo_bloqueo"],
                    parametros["observaciones"], fila["evento"].pk if fila["evento"] else 0,
                    usar_motivo_bloqueo=True,
                )
            elif fila["clase"]:
                anular_clase(usuario, fila["clase"].pk, motivo)
            elif fila["reserva"]:
                anular_reserva(usuario, fila["reserva"].pk, motivo)
            else:
                anular_bloqueo(usuario, fila["bloqueo"].pk, motivo, fila["cancha"], fila["fecha"], fila["hora"])

        ahora = timezone.localtime()
        if any(timezone.make_aware(datetime.combine(fila["fecha"], fila["hora"])) <= ahora for fila in previa["acciones"]):
            raise ValidationError("Un turno alcanzó su hora de inicio. No se aplicó la operación; revisá la vista previa.")
    return previa
