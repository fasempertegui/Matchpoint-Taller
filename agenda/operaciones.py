import hashlib
import json
from calendar import monthrange
from datetime import datetime, time, timedelta

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
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from reservas.servicios import anular_reserva, validar_anulacion_reserva


def _preparar_operacion_dia(sede, fecha, parametros, mensual=False):
    ahora = timezone.localtime()
    if not mensual and not ahora.date() <= fecha <= fecha_maxima_agenda():
        raise ValidationError("Elegí una fecha desde hoy hasta un año después, inclusive.")
    operacion = parametros["operacion"]
    if operacion not in ("liberar", "bloquear"):
        raise ValidationError("Elegí una operación válida.")
    if operacion == "bloquear" and fecha > fecha_maxima_eventos():
        maxima = fecha_maxima_eventos()
        raise ValidationError(f"Sólo se pueden crear bloqueos hasta el {maxima:%d/%m/%Y}, inclusive.")
    canchas = list(Cancha.objects.filter(sede=sede, pk__in=parametros["canchas"]).order_by("pk"))
    if not canchas or len(canchas) != len(parametros["canchas"]):
        raise ValidationError("Revisá las canchas de la sede seleccionada.")
    if operacion == "bloquear" and (
        sede.estado != Sede.Estado.ACTIVA or any(cancha.estado != Cancha.Estado.ACTIVA for cancha in canchas)
    ):
        raise ValidationError("Para bloquear, la sede y todas las canchas seleccionadas deben estar activas.")
    if operacion == "bloquear" and parametros["motivo_bloqueo"] not in Bloqueo.Motivo.values:
        raise ValidationError("Elegí un motivo de bloqueo válido.")

    corte = time.fromisoformat(parametros["hora_desde"]) if parametros["alcance"] == "desde" else time.min
    horario = sede.horarios.filter(dia_semana=fecha.isoweekday()).first()
    franjas = []
    if horario:
        franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
        if horario.hora_inicio_2 is not None:
            franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
    hasta = time.fromisoformat(parametros["hora_hasta"]) if parametros["hora_hasta"] else None
    if hasta and (
        parametros["alcance"] != "desde" or hasta <= corte
        or hasta.minute or hasta.second or hasta.microsecond
        or (not mensual and not any(inicio < hasta <= fin for inicio, fin in franjas))
    ):
        raise ValidationError("La hora de fin debe ser posterior al inicio y coincidir con el fin de un turno habilitado.")
    horas_habilitadas = {
        hora for hora in range(23)
        if time(hora) >= corte and (hasta is None or time(hora + 1) <= hasta)
        and any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
    }
    eventos = Evento.objects.filter(
        turno__cancha__in=canchas, turno__fecha=fecha, turno__hora_inicio__gte=corte,
    ).exclude(estado=Evento.Estado.ANULADO).select_related("turno", "reserva__organizador", "bloqueo", "clase").prefetch_related(
        "clase__profesores", "clase__alumnos",
    )
    if hasta is not None:
        eventos = eventos.filter(turno__hora_inicio__lt=hasta)
    ocupacion = {(evento.turno.cancha_id, evento.turno.hora_inicio.hour): evento for evento in eventos}

    filas = []
    for cancha in canchas:
        horas = horas_habilitadas | {hora for cancha_id, hora in ocupacion if cancha_id == cancha.pk}
        for hora in sorted(horas):
            inicio = timezone.make_aware(datetime.combine(fecha, time(hora)))
            evento = ocupacion.get((cancha.pk, hora))
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
            elif evento and evento.tipo == Evento.Tipo.CLASE and (
                parametros["excluir_clases_generadas"] if evento.clase.es_generada
                else parametros["excluir_clases_manuales"]
            ):
                fila["conservado"] = "Clase excluida"
            elif evento and evento.tipo == Evento.Tipo.RESERVA and parametros["excluir_reservas"]:
                fila["conservado"] = "Reserva excluida"
            elif evento and evento.tipo == Evento.Tipo.BLOQUEO and operacion == "bloquear":
                fila["conservado"] = "Bloqueo existente"
            elif evento and evento.tipo == Evento.Tipo.BLOQUEO and parametros["excluir_bloqueos"]:
                fila["conservado"] = "Bloqueo excluido"
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
                    [vinculo.profesor_id, vinculo.estado, vinculo.actualizado_en.isoformat()]
                    for vinculo in fila["clase"].profesores.all()
                ]),
                "participantes": sorted([
                    [vinculo.usuario_id, vinculo.estado, vinculo.actualizado_en.isoformat()]
                    for vinculo in fila["clase"].alumnos.all()
                ]),
            }
            for fila in filas if fila["clase"] is not None
        ],
        "invitados": [list(fila["reserva"].invitados.order_by("usuario_id").values_list("usuario_id", "respuesta", "actualizado_en")) for fila in filas if fila["reserva"]],
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
        "anulaciones": anulaciones, "reservas_a_anular": reservas_a_anular,
        "clases_a_anular": sum(fila["clase"] is not None for fila in acciones),
        "bloqueos_a_crear": len(acciones) if operacion == "bloquear" else 0,
        "libres_sin_accion": sum(not fila["evento"] and not fila["accion"] for fila in filas),
        "huella": huella,
    }


def preparar_operacion(sede, fecha, parametros, fecha_hasta=None):
    if fecha_hasta is None:
        return _preparar_operacion_dia(sede, fecha, parametros)
    if parametros["operacion"] != "liberar":
        raise ValidationError("Las acciones del mes sólo permiten anular y liberar.")
    if (
        fecha.day != 1 or fecha_hasta != fecha.replace(day=monthrange(fecha.year, fecha.month)[1])
        or fecha < max(FECHA_INICIO_OPERACIONES, timezone.localdate().replace(day=1))
        or fecha_hasta > fecha_maxima_eventos()
    ):
        raise ValidationError("Elegí un mes completo dentro del calendario operativo.")
    if parametros["hora_hasta"]:
        hasta = time.fromisoformat(parametros["hora_hasta"])
        franjas = []
        for horario in sede.horarios.all():
            franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
            if horario.hora_inicio_2 is not None:
                franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
        if not any(inicio < hasta <= fin for inicio, fin in franjas):
            raise ValidationError("La hora de fin debe coincidir con el fin de un turno habilitado.")
    dias = [
        _preparar_operacion_dia(sede, fecha + timedelta(days=numero), parametros, mensual=True)
        for numero in range((fecha_hasta - fecha).days + 1)
    ]
    return {
        "acciones": [fila for dia in dias for fila in dia["acciones"]],
        "conservados": [fila for dia in dias for fila in dia["conservados"]],
        "canchas": dias[0]["canchas"],
        **{
            campo: sum(dia[campo] for dia in dias)
            for campo in ("anulaciones", "reservas_a_anular", "clases_a_anular", "bloqueos_a_crear", "libres_sin_accion")
        },
        "huella": hashlib.sha256(json.dumps([dia["huella"] for dia in dias]).encode()).hexdigest(),
    }


@transaction.atomic
def ejecutar_operacion(usuario, sede_id, fecha, parametros, huella, fecha_hasta=None):
    usuario = exigir_administracion_clases(usuario)
    sede = Sede.objects.get(pk=sede_id)
    seleccion = preparar_operacion(sede, fecha, parametros, fecha_hasta)
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
            usuarios_ids.update(fila["reserva"].invitados.values_list("usuario_id", flat=True))
    usuarios = bloquear_usuarios_clase(usuarios_ids)
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    sede = Sede.objects.select_for_update().get(pk=sede_id)
    list(Cancha.objects.select_for_update().filter(sede=sede, pk__in=parametros["canchas"]).order_by("pk"))
    # Todos los turnos se bloquean antes de los eventos, igual que en las acciones individuales.
    turnos = list(Turno.objects.select_for_update().filter(
        cancha_id__in=parametros["canchas"], fecha__range=(fecha, fecha_hasta or fecha),
    ).order_by("pk"))
    list(Evento.objects.select_for_update().filter(turno__in=turnos).order_by("pk"))
    previa = preparar_operacion(sede, fecha, parametros, fecha_hasta)
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
