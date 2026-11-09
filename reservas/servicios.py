from common.validaciones import validar_motivo

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from bloqueos.models import Bloqueo
from common.fechas import validar_inicio_evento
from usuarios.models import Rol, Usuario

from .disponibilidad import consultar_disponibilidad
from .models import Evento, Reserva, Turno


def exigir_acceso_reservas(usuario):
    if usuario is None or not usuario.is_authenticated:
        raise PermissionDenied
    roles = set(usuario.roles.values_list("rol__codigo", flat=True))
    if (
        not usuario.is_active
        or usuario.debe_cambiar_contrasena
        or not roles.intersection((Rol.ADMINISTRADOR, Rol.RESERVAS))
    ):
        raise PermissionDenied
    return Rol.ADMINISTRADOR in roles


def validar_turno_seleccionado(disponibilidad, identificador):
    turno = next((turno for turno in disponibilidad["turnos"] if turno.pk == identificador), None)
    if turno is None:
        raise ValidationError("El turno ya no está disponible. Elegí nuevamente.")
    if not any(
        turno.hora_inicio >= inicio and turno.hora_fin <= fin
        for inicio, fin in disponibilidad["franjas"]
    ):
        raise ValidationError("El turno debe estar dentro de una franja de funcionamiento.")
    return turno


@transaction.atomic
def registrar_reserva(registrado_por, organizador, cancha, fecha, turno_id, precio_mostrado, observaciones):
    from .comercial import preparar_reserva, confirmar_reserva
    turno = Turno.objects.get(pk=turno_id, cancha=cancha, fecha=fecha)
    revision = preparar_reserva(registrado_por, {
        "organizador": organizador.pk, "cancha": cancha.pk, "fecha": fecha.isoformat(),
        "hora": turno.hora_inicio.hour, "modalidad": "normal", "invitados": [], "observaciones": observaciones,
    })
    if revision["total"] != precio_mostrado:
        raise ValidationError("El precio cambió. Revisá nuevamente la reserva.")
    return confirmar_reserva(registrado_por, revision["confirmacion"])


def validar_anulacion_reserva(reserva, es_administrador, ahora):
    if reserva.evento.tipo != Evento.Tipo.RESERVA:
        raise ValidationError("El evento no corresponde a una reserva.")
    if reserva.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden anular reservas Programadas.")
    turno = reserva.evento.turno
    inicio = timezone.make_aware(
        datetime.combine(turno.fecha, turno.hora_inicio),
        timezone.get_current_timezone(),
    )
    if ahora >= inicio:
        raise ValidationError("Sólo se puede anular una reserva antes de su inicio.")


def _bloquear_reserva(reserva_id):
    reserva = Reserva.objects.select_related("evento").get(pk=reserva_id)
    # El turno coordina la ocupación y se bloquea antes del evento.
    turno = Turno.objects.select_for_update().get(pk=reserva.evento.turno_id)
    reserva.evento = Evento.objects.select_for_update().get(pk=reserva.evento_id)
    reserva.evento.turno = turno
    return reserva


@transaction.atomic
def anular_reserva(anulado_por, reserva_id, motivo, *, motivo_bloqueo=None):
    from .comercial import bloquear_reserva_personas
    anulado_por, es_administrador, reserva, _, _ = bloquear_reserva_personas(anulado_por, reserva_id)
    if motivo_bloqueo is not None:
        if not es_administrador:
            raise PermissionDenied
        if motivo_bloqueo not in Bloqueo.Motivo.values:
            raise ValidationError("Elegí un motivo de bloqueo válido.")
        motivo = Bloqueo.Motivo(motivo_bloqueo).label
    motivo = motivo.strip()
    validar_motivo(motivo)

    if not es_administrador and reserva.organizador_id != anulado_por.pk:
        raise PermissionDenied
    ahora = timezone.localtime()
    validar_anulacion_reserva(reserva, es_administrador, ahora)

    evento = reserva.evento
    evento.estado = Evento.Estado.ANULADO
    evento.anulado_en = ahora
    evento.anulado_por = anulado_por
    evento.motivo_anulacion = motivo
    evento.save(update_fields=["estado", "anulado_en", "anulado_por", "motivo_anulacion", "actualizado_en"])
    reserva.anulada_por_organizador = not es_administrador
    if reserva.es_con_membresia:
        inicio = timezone.make_aware(datetime.combine(reserva.evento.turno.fecha, reserva.evento.turno.hora_inicio))
        reserva.computa_hora_membresia = not es_administrador and inicio - ahora <= timedelta(hours=2)
    reserva.save(update_fields=["anulada_por_organizador", "computa_hora_membresia"])
    return reserva


def validar_finalizacion_reserva(reserva, ahora):
    if reserva.evento.tipo != Evento.Tipo.RESERVA:
        raise ValidationError("El evento no corresponde a una reserva.")
    if reserva.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden finalizar reservas Programadas.")
    turno = reserva.evento.turno
    fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
    if ahora < fin:
        raise ValidationError("Sólo se puede finalizar una reserva cuando terminó su turno.")


@transaction.atomic
def finalizar_reserva(reserva_id, usuario=None):
    with contexto_auditoria(usuario, origen="aplicacion" if usuario is not None else "tarea"):
        if usuario is not None:
            usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
            if not exigir_acceso_reservas(usuario):
                raise PermissionDenied

        reserva = _bloquear_reserva(reserva_id)
        ahora = timezone.localtime()
        validar_finalizacion_reserva(reserva, ahora)

        evento = reserva.evento
        evento.estado = Evento.Estado.FINALIZADO
        evento.finalizado_en = ahora
        evento.save(update_fields=["estado", "finalizado_en", "actualizado_en"])
        return reserva


def finalizar_reservas_vencidas():
    limite_inicio = timezone.localtime() - timedelta(hours=1)
    pendientes = Reserva.objects.filter(
        evento__tipo=Evento.Tipo.RESERVA,
        evento__estado=Evento.Estado.PROGRAMADO,
    ).filter(
        Q(evento__turno__fecha__lt=limite_inicio.date())
        | Q(evento__turno__fecha=limite_inicio.date(), evento__turno__hora_inicio__lte=limite_inicio.time())
    ).order_by("pk").values_list("pk", flat=True)

    finalizadas = 0
    for reserva_id in pendientes.iterator(chunk_size=500):
        try:
            finalizar_reserva(reserva_id)
        except ValidationError:
            continue
        else:
            finalizadas += 1
    return finalizadas
