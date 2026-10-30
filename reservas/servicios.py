from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario

from .disponibilidad import consultar_disponibilidad
from .models import Evento, Reserva, Turno


def exigir_acceso_reservas(usuario):
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
    participantes = {registrado_por.pk, organizador.pk}
    # La desactivación de cuentas también bloquea primero los administradores activos.
    list(
        Usuario.objects.select_for_update(of=("self",))
        .filter(pk__in=participantes, is_active=True, roles__rol__codigo=Rol.ADMINISTRADOR)
        .order_by("pk")
    )
    usuarios = {
        usuario.pk: usuario
        for usuario in Usuario.objects.select_for_update().filter(pk__in=participantes).order_by("pk")
    }
    registrado_por = usuarios[registrado_por.pk]
    organizador = usuarios[organizador.pk]
    es_administrador = exigir_acceso_reservas(registrado_por)
    if not es_administrador and organizador.pk != registrado_por.pk:
        raise PermissionDenied
    if not organizador.is_active:
        raise ValidationError("El organizador debe estar activo para registrar la reserva.")
    if not organizador.puede_reservar:
        raise ValidationError("El organizador debe tener el rol Reservas o Administrador para registrar la reserva.")
    reservas_programadas = Reserva.objects.filter(
        organizador=organizador,
        evento__estado=Evento.Estado.PROGRAMADO,
    ).count()
    if reservas_programadas >= 5:
        raise ValidationError("El organizador ya tiene el máximo de cinco reservas Programadas.")

    disponibilidad = consultar_disponibilidad(cancha, fecha)
    turno = validar_turno_seleccionado(disponibilidad, turno_id)
    turno = Turno.objects.select_for_update().get(pk=turno.pk, cancha=cancha, fecha=fecha)
    ahora = timezone.localtime()
    if fecha < ahora.date() or (fecha == ahora.date() and turno.hora_inicio <= ahora.time()):
        raise ValidationError("La reserva debe comenzar en un horario futuro. Elegí nuevamente.")
    if Evento.objects.filter(turno=turno).exclude(estado=Evento.Estado.ANULADO).exists():
        raise ValidationError("El turno fue ocupado por otra actividad. Elegí nuevamente.")
    precio = disponibilidad["precio_por_turno"]
    if precio != precio_mostrado:
        raise ValidationError("El precio por turno cambió. Revisá el nuevo total y confirmá nuevamente.")

    evento = Evento.objects.create(
        turno=turno,
        tipo=Evento.Tipo.RESERVA,
        registrado_por=registrado_por,
        observaciones=observaciones,
    )
    reserva = Reserva.objects.create(
        evento=evento,
        organizador=organizador,
        precio_por_turno_aplicado=precio,
    )
    return reserva


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
    if not es_administrador and ahora > inicio - timedelta(hours=1):
        raise ValidationError("Para anular tu reserva debe faltar al menos una hora para el inicio del turno.")


def _bloquear_reserva(reserva_id):
    reserva = Reserva.objects.select_related("evento").get(pk=reserva_id)
    # El turno coordina la ocupación y se bloquea antes del evento.
    turno = Turno.objects.select_for_update().get(pk=reserva.evento.turno_id)
    reserva.evento = Evento.objects.select_for_update().get(pk=reserva.evento_id)
    reserva.evento.turno = turno
    return reserva


@transaction.atomic
def anular_reserva(anulado_por, reserva_id, motivo):
    anulado_por = Usuario.objects.select_for_update().get(pk=anulado_por.pk)
    es_administrador = exigir_acceso_reservas(anulado_por)
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError("Indicá el motivo de la anulación.")
    if len(motivo) < 25:
        raise ValidationError("El motivo de anulación debe tener al menos 25 caracteres.")

    reserva = _bloquear_reserva(reserva_id)
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
    reserva.save(update_fields=["anulada_por_organizador"])
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
