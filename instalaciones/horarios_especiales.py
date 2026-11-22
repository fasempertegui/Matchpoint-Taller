import hashlib
import json
from datetime import datetime

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from bloqueos.servicios import anular_bloqueo
from clases.models import Feriado
from clases.permisos import exigir_administracion_clases
from clases.servicios import anular_clase, bloquear_calendario_clases, bloquear_usuarios_clase
from common.fechas import fecha_maxima_feriados
from reservas.models import Evento, Turno
from reservas.servicios import anular_reserva

from .horarios import franjas_horario
from .models import Sede, SedeHorarioEspecial
from .servicios import usuarios_de_eventos


SAL_CONFIRMACION = "instalaciones.horario-especial"


def _revisar(horario, quitar):
    vigente = SedeHorarioEspecial.objects.filter(sede_id=horario.sede_id, fecha=horario.fecha).first()
    if (vigente.pk if vigente else None) != horario.pk or (quitar and vigente is None):
        raise ValidationError("El horario especial de esa fecha cambió o ya está registrado. Revisá nuevamente.")
    if quitar:
        habitual = horario.sede.horarios.filter(dia_semana=horario.fecha.isoweekday()).first()
        franjas = franjas_horario(habitual)
    else:
        horario.full_clean()
        if horario.fecha > fecha_maxima_feriados():
            raise ValidationError("El horario especial puede registrarse hasta cinco años después de hoy.")
        franjas = franjas_horario(horario)

    feriado = Feriado.objects.filter(fecha=horario.fecha).first()
    ahora = timezone.localtime()
    eventos = []
    conflictos = []
    instantaneas = []
    candidatos = Evento.objects.filter(
        turno__cancha__sede_id=horario.sede_id, turno__fecha=horario.fecha,
        estado=Evento.Estado.PROGRAMADO,
    ).select_related("turno__cancha__sede", "reserva", "clase", "bloqueo").prefetch_related(
        "clase__profesores", "clase__alumnos", "reserva__invitados",
    ).order_by("turno__hora_inicio", "turno__cancha_id", "pk")

    for evento in candidatos:
        turno = evento.turno
        if any(inicio <= turno.hora_inicio and turno.hora_fin <= fin for inicio, fin in franjas):
            continue
        inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
        fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
        referencia = f"{evento.get_tipo_display()} en {turno.cancha.nombre} a las {turno.hora_inicio:%H:%M}"
        if inicio <= ahora:
            if ahora < fin:
                conflictos.append(f"{referencia} está en curso y quedaría fuera del horario.")
        elif feriado and evento.tipo in (Evento.Tipo.RESERVA, Evento.Tipo.BLOQUEO):
            conflictos.append(f"{referencia} quedaría fuera del horario. Resolvé el conflicto antes de guardar.")
        else:
            eventos.append(evento)
            instantaneas.append([
                evento.pk, turno.pk, evento.actualizado_en,
                sorted(usuarios_de_eventos((evento,))),
            ])

    datos = {
        "registro": horario.pk, "sede": horario.sede_id, "fecha": horario.fecha,
        "version": vigente.actualizado_en if vigente else None,
        "quitar": quitar, "motivo": vigente.motivo if quitar else horario.motivo,
        "franjas": franjas, "feriado": feriado.pk if feriado else None,
        "eventos": instantaneas, "conflictos": conflictos,
    }
    return {
        "eventos": eventos, "conflictos": conflictos,
        "huella": hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest(),
    }


def preparar_horario_especial(actor, horario, *, quitar=False):
    actor = exigir_administracion_clases(actor)
    revision = _revisar(horario, quitar)
    revision["confirmacion"] = signing.dumps(
        {"actor": actor.pk, "huella": revision["huella"]}, salt=SAL_CONFIRMACION,
    )
    return revision


@transaction.atomic
def guardar_horario_especial(actor, horario, *, confirmacion=None, quitar=False):
    actor = exigir_administracion_clases(actor)
    inicial = _revisar(horario, quitar)
    usuarios = bloquear_usuarios_clase(usuarios_de_eventos(inicial["eventos"]) | {actor.pk})
    actor = exigir_administracion_clases(usuarios.get(actor.pk))
    bloquear_calendario_clases(horario.fecha)
    horario.sede = Sede.objects.select_for_update().get(pk=horario.sede_id)
    turnos = list(Turno.objects.select_for_update().filter(
        pk__in=[evento.turno_id for evento in inicial["eventos"]],
    ).order_by("pk"))
    list(Evento.objects.select_for_update().filter(turno__in=turnos).order_by("pk"))
    revision = _revisar(horario, quitar)
    if revision["huella"] != inicial["huella"]:
        raise ValidationError("Las actividades o el horario cambiaron. Revisá nuevamente la operación.")
    if revision["conflictos"]:
        raise ValidationError(revision["conflictos"])
    if revision["eventos"] or confirmacion:
        try:
            datos = signing.loads(confirmacion or "", salt=SAL_CONFIRMACION, max_age=900)
        except signing.BadSignature:
            raise ValidationError("Revisá las actividades afectadas antes de confirmar.") from None
        if datos != {"actor": actor.pk, "huella": revision["huella"]}:
            raise ValidationError("La vista previa ya no coincide con el horario o las actividades.")

    motivo = "Actividad anulada por cambio de horario especial de la sede"
    with contexto_auditoria(actor):
        for evento in revision["eventos"]:
            if evento.tipo == Evento.Tipo.CLASE:
                anular_clase(actor, evento.clase.pk, motivo)
            elif evento.tipo == Evento.Tipo.RESERVA:
                anular_reserva(actor, evento.reserva.pk, motivo)
            else:
                turno = evento.turno
                anular_bloqueo(actor, evento.bloqueo.pk, motivo, turno.cancha, turno.fecha, turno.hora_inicio)
        if quitar:
            horario.delete()
        else:
            horario.save()
        ahora = timezone.localtime()
        if any(
            timezone.make_aware(datetime.combine(evento.turno.fecha, evento.turno.hora_inicio)) <= ahora
            for evento in revision["eventos"]
        ):
            raise ValidationError("Un turno alcanzó su inicio. Revisá nuevamente la operación.")
    return horario
