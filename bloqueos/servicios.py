from datetime import datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from clases.models import Clase
from clases.servicios import anular_clase, bloquear_usuarios_clase
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from reservas.servicios import anular_reserva, exigir_acceso_reservas
from usuarios.models import Usuario

from .models import Bloqueo


def validar_inicio_bloqueo(fecha, hora, ahora):
    if not FECHA_INICIO_OPERACIONES <= fecha <= fecha_maxima_agenda():
        raise ValidationError("La fecha está fuera del calendario operativo.")
    if hora not in tuple(time(valor) for valor in range(23)):
        raise ValidationError("El turno debe comenzar en punto entre las 00:00 y las 22:00.")
    if timezone.make_aware(datetime.combine(fecha, hora)) <= ahora:
        raise ValidationError("Sólo se puede bloquear un turno antes de su inicio.")


def validar_anulacion_bloqueo(bloqueo, ahora):
    evento = bloqueo.evento
    if evento.tipo != Evento.Tipo.BLOQUEO or evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden anular bloqueos Programados.")
    turno = evento.turno
    if timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio)) <= ahora:
        raise ValidationError("Sólo se puede anular un bloqueo antes de su inicio.")


@transaction.atomic
def registrar_bloqueo(registrado_por, cancha, fecha, hora, motivo, observaciones, evento_esperado, motivo_anulacion=""):
    if not exigir_acceso_reservas(registrado_por):
        raise PermissionDenied
    clase_revisada = Clase.objects.filter(
        evento_id=evento_esperado,
        evento__tipo=Evento.Tipo.CLASE,
        evento__turno__cancha_id=cancha.pk,
        evento__turno__fecha=fecha,
        evento__turno__hora_inicio=hora,
    ).first()
    profesores_ids = set()
    participantes_ids = set()
    if clase_revisada is not None:
        profesores_ids = set(clase_revisada.profesores.values_list("profesor_id", flat=True))
        participantes_ids = set(clase_revisada.alumnos.values_list("usuario_id", flat=True))
    usuarios = bloquear_usuarios_clase(profesores_ids | participantes_ids | {registrado_por.pk})
    registrado_por = usuarios.get(registrado_por.pk)
    if registrado_por is None or not exigir_acceso_reservas(registrado_por):
        raise PermissionDenied
    if motivo not in Bloqueo.Motivo.values:
        raise ValidationError("Elegí un motivo de bloqueo válido.")

    sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    if sede.estado != Sede.Estado.ACTIVA or cancha.estado != Cancha.Estado.ACTIVA:
        raise ValidationError("La sede y la cancha deben estar activas para registrar un bloqueo.")
    validar_inicio_bloqueo(fecha, hora, timezone.localtime())
    horario = sede.horarios.filter(dia_semana=fecha.isoweekday()).first()
    franjas = []
    if horario is not None:
        franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
        if horario.hora_inicio_2 is not None:
            franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
    fin = (datetime.combine(fecha, hora) + timedelta(hours=1)).time()
    if not any(hora >= inicio and fin <= limite for inicio, limite in franjas):
        raise ValidationError("El bloqueo debe estar dentro de una franja de funcionamiento de la sede.")

    with contexto_auditoria(registrado_por):
        # La sede coordina la creación del turno con la preparación para reservas.
        turno, _ = Turno.objects.get_or_create(cancha=cancha, fecha=fecha, hora_inicio=hora)
        turno = Turno.objects.select_for_update().get(pk=turno.pk)
        evento = Evento.objects.select_for_update().filter(turno=turno).exclude(estado=Evento.Estado.ANULADO).first()
        if (evento.pk if evento else 0) != evento_esperado:
            raise ValidationError("La actividad del turno cambió. Revisá la agenda antes de confirmar.")
        if evento:
            if evento.tipo == Evento.Tipo.RESERVA:
                evento = anular_reserva(registrado_por, evento.reserva.pk, motivo_anulacion).evento
            elif evento.tipo == Evento.Tipo.CLASE:
                clase = Clase.objects.select_for_update().get(evento=evento)
                if (
                    clase_revisada is None or clase.pk != clase_revisada.pk
                    or profesores_ids != set(clase.profesores.values_list("profesor_id", flat=True))
                    or participantes_ids != set(clase.alumnos.values_list("usuario_id", flat=True))
                ):
                    raise ValidationError("Las asignaciones de la clase cambiaron. Revisá la agenda antes de confirmar.")
                evento = anular_clase(registrado_por, clase.pk, motivo_anulacion).evento
            else:
                raise ValidationError("El turno ya está ocupado por otra actividad.")

        validar_inicio_bloqueo(fecha, hora, timezone.localtime())
        if Evento.objects.filter(turno=turno).exclude(estado=Evento.Estado.ANULADO).exists():
            raise ValidationError("El turno ya está ocupado por otra actividad.")
        evento_bloqueo = Evento.objects.create(
            turno=turno,
            tipo=Evento.Tipo.BLOQUEO,
            registrado_por=registrado_por,
            observaciones=observaciones.strip(),
        )
        bloqueo = Bloqueo.objects.create(evento=evento_bloqueo, motivo=motivo, evento_origen=evento)
        validar_inicio_bloqueo(fecha, hora, timezone.localtime())
    return bloqueo


@transaction.atomic
def anular_bloqueo(anulado_por, bloqueo_id, motivo, cancha, fecha, hora):
    anulado_por = Usuario.objects.select_for_update().get(pk=anulado_por.pk)
    if not exigir_acceso_reservas(anulado_por):
        raise PermissionDenied
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError("Indicá el motivo de la anulación.")
    bloqueo = Bloqueo.objects.select_related("evento").filter(pk=bloqueo_id).first()
    if bloqueo is None:
        raise ValidationError("El bloqueo ya no está disponible. Revisá la agenda.")
    turno = Turno.objects.select_for_update().get(pk=bloqueo.evento.turno_id)
    if (turno.cancha_id, turno.fecha, turno.hora_inicio) != (cancha.pk, fecha, hora):
        raise ValidationError("El bloqueo no corresponde al turno seleccionado.")
    bloqueo.evento = Evento.objects.select_for_update().get(pk=bloqueo.evento_id)
    bloqueo.evento.turno = turno
    ahora = timezone.localtime()
    validar_anulacion_bloqueo(bloqueo, ahora)
    evento = bloqueo.evento
    evento.estado = Evento.Estado.ANULADO
    evento.anulado_por = anulado_por
    evento.anulado_en = ahora
    evento.motivo_anulacion = motivo
    evento.save(update_fields=["estado", "anulado_por", "anulado_en", "motivo_anulacion", "actualizado_en"])
    return bloqueo
