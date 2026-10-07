from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from usuarios.models import Rol, Usuario

from .disponibilidad import consultar_disponibilidad
from .models import Reserva, ReservaTurno, Turno


def exigir_acceso_reservas(usuario):
    roles = set(usuario.roles.values_list("rol__codigo", flat=True))
    if (
        not usuario.is_active
        or usuario.debe_cambiar_contrasena
        or not roles.intersection((Rol.ADMINISTRADOR, Rol.RESERVAS))
    ):
        raise PermissionDenied
    return Rol.ADMINISTRADOR in roles


def validar_turnos_seleccionados(disponibilidad, identificadores):
    if not identificadores:
        raise ValidationError("Seleccioná al menos un turno.")
    if len(identificadores) != len(set(identificadores)):
        raise ValidationError("No se puede seleccionar un mismo turno más de una vez.")
    disponibles = {turno.pk: turno for turno in disponibilidad["turnos"]}
    if any(identificador not in disponibles for identificador in identificadores):
        raise ValidationError("Uno o más turnos ya no están disponibles. Elegí nuevamente.")
    turnos = sorted(
        (disponibles[identificador] for identificador in identificadores),
        key=lambda turno: turno.hora_inicio,
    )
    if any(anterior.hora_fin != siguiente.hora_inicio for anterior, siguiente in zip(turnos, turnos[1:])):
        raise ValidationError("Los turnos seleccionados deben ser consecutivos.")
    if not any(
        turnos[0].hora_inicio >= inicio and turnos[-1].hora_fin <= fin
        for inicio, fin in disponibilidad["franjas"]
    ):
        raise ValidationError("Todos los turnos deben estar dentro de una misma franja de funcionamiento.")
    return turnos


@transaction.atomic
def registrar_reserva(registrado_por, organizador, cancha, fecha, identificadores, precio_mostrado, observaciones):
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

    disponibilidad = consultar_disponibilidad(cancha, fecha)
    list(Turno.objects.select_for_update().filter(
        pk__in=identificadores, cancha=cancha, fecha=fecha,
    ).order_by("pk"))
    turnos = validar_turnos_seleccionados(disponibilidad, identificadores)
    ahora = timezone.localtime()
    if fecha < ahora.date() or (fecha == ahora.date() and turnos[0].hora_inicio <= ahora.time()):
        raise ValidationError("La reserva debe comenzar en un horario futuro. Elegí nuevamente.")
    if ReservaTurno.objects.filter(
        turno__in=turnos,
        reserva__estado__in=(Reserva.Estado.PROGRAMADA, Reserva.Estado.FINALIZADA),
    ).exists():
        raise ValidationError("Uno o más turnos fueron reservados. Elegí nuevamente.")
    precio = disponibilidad["precio_por_turno"]
    if precio != precio_mostrado:
        raise ValidationError("El precio por turno cambió. Revisá el nuevo total y confirmá nuevamente.")

    reserva = Reserva.objects.create(
        organizador=organizador,
        registrado_por=registrado_por,
        precio_por_turno_aplicado=precio,
        observaciones=observaciones,
    )
    ReservaTurno.objects.bulk_create([
        ReservaTurno(reserva=reserva, turno=turno) for turno in turnos
    ])
    return reserva, precio * len(turnos)


def validar_anulacion_reserva(reserva, primer_turno, es_administrador, ahora):
    if reserva.estado != Reserva.Estado.PROGRAMADA:
        raise ValidationError("Sólo se pueden anular reservas Programadas.")
    if primer_turno is None:
        raise ValidationError("La reserva no tiene turnos asociados.")
    inicio = timezone.make_aware(
        datetime.combine(primer_turno.fecha, primer_turno.hora_inicio),
        timezone.get_current_timezone(),
    )
    if ahora >= inicio:
        raise ValidationError("Sólo se puede anular una reserva antes de su inicio.")
    if not es_administrador and ahora > inicio - timedelta(hours=1):
        raise ValidationError("Para anular tu reserva debe faltar al menos una hora para el inicio del primer turno.")


@transaction.atomic
def anular_reserva(anulado_por, reserva_id, motivo):
    anulado_por = Usuario.objects.select_for_update().get(pk=anulado_por.pk)
    es_administrador = exigir_acceso_reservas(anulado_por)
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError("Indicá el motivo de la anulación.")
    if len(motivo) < 25:
        raise ValidationError("El motivo de anulación debe tener al menos 25 caracteres.")

    # Los turnos coordinan la ocupación con el registro y se bloquean antes de la cabecera.
    turnos = list(
        Turno.objects.select_for_update(of=("self",))
        .filter(reservas_turnos__reserva_id=reserva_id)
        .order_by("pk")
    )
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    if not es_administrador and reserva.organizador_id != anulado_por.pk:
        raise PermissionDenied
    primer_turno = min(turnos, key=lambda turno: (turno.fecha, turno.hora_inicio)) if turnos else None
    ahora = timezone.localtime()
    validar_anulacion_reserva(reserva, primer_turno, es_administrador, ahora)

    reserva.estado = Reserva.Estado.ANULADA
    reserva.anulado_en = ahora
    reserva.anulado_por = anulado_por
    reserva.motivo_anulacion = motivo
    reserva.save(update_fields=["estado", "anulado_en", "anulado_por", "motivo_anulacion"])
    return reserva


def validar_finalizacion_reserva(reserva, ultimo_turno, ahora):
    if reserva.estado != Reserva.Estado.PROGRAMADA:
        raise ValidationError("Sólo se pueden finalizar reservas Programadas.")
    if ultimo_turno is None:
        raise ValidationError("La reserva no tiene turnos asociados.")
    fin = timezone.make_aware(datetime.combine(ultimo_turno.fecha, ultimo_turno.hora_fin))
    if ahora < fin:
        raise ValidationError("Sólo se puede finalizar una reserva cuando terminó su último turno.")


@transaction.atomic
def finalizar_reserva(reserva_id, usuario=None):
    if usuario is not None:
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
        if not exigir_acceso_reservas(usuario):
            raise PermissionDenied

    # La anulación también bloquea los turnos antes de la cabecera.
    turnos = list(
        Turno.objects.select_for_update(of=("self",))
        .filter(reservas_turnos__reserva_id=reserva_id)
        .order_by("pk")
    )
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    ultimo_turno = max(turnos, key=lambda turno: (turno.fecha, turno.hora_fin)) if turnos else None
    ahora = timezone.localtime()
    validar_finalizacion_reserva(reserva, ultimo_turno, ahora)

    reserva.estado = Reserva.Estado.FINALIZADA
    reserva.finalizado_en = ahora
    reserva.save(update_fields=["estado", "finalizado_en"])
    return reserva


def finalizar_reservas_vencidas():
    ahora = timezone.localtime()
    # Todos los turnos de una reserva pertenecen a la misma fecha.
    pendientes = Reserva.objects.filter(estado=Reserva.Estado.PROGRAMADA).annotate(
        fecha_fin=Max("detalles__turno__fecha"),
        hora_fin=Max("detalles__turno__hora_fin"),
    ).filter(
        Q(fecha_fin__lt=ahora.date())
        | Q(fecha_fin=ahora.date(), hora_fin__lte=ahora.time())
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
