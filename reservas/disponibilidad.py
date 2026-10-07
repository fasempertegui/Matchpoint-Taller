from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from instalaciones.models import Cancha, Sede

from .models import Evento, Turno


def validar_fecha_reserva(fecha):
    hoy = timezone.localdate()
    if not hoy <= fecha <= hoy + timedelta(days=14):
        raise ValidationError("Elegí una fecha desde hoy hasta catorce días después, inclusive.")


@transaction.atomic
def consultar_disponibilidad(cancha, fecha):
    validar_fecha_reserva(fecha)

    # La sede coordina la preparación con los cambios de horarios y precios.
    sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    if sede.estado != Sede.Estado.ACTIVA or cancha.estado != Cancha.Estado.ACTIVA:
        raise ValidationError("La sede y la cancha deben estar activas para consultar disponibilidad.")
    precio = sede.precio_reserva_vigente
    if precio is None:
        raise ValidationError("La sede necesita un precio por turno configurado para ofrecer turnos.")

    horario = sede.horarios.filter(dia_semana=fecha.isoweekday()).first()
    franjas = []
    if horario is not None:
        franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
        if horario.hora_inicio_2 is not None:
            franjas.append((horario.hora_inicio_2, horario.hora_fin_2))

    inicios_habilitados = [
        time(hora)
        for hora in range(23)
        if any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
    ]
    inicios_existentes = set(
        Turno.objects.filter(cancha=cancha, fecha=fecha).values_list("hora_inicio", flat=True)
    )
    Turno.objects.bulk_create([
        Turno(
            cancha=cancha,
            fecha=fecha,
            hora_inicio=inicio,
        )
        for inicio in inicios_habilitados
        if inicio not in inicios_existentes
    ])

    turnos_libres = Turno.objects.filter(
        cancha=cancha,
        fecha=fecha,
        hora_inicio__in=inicios_habilitados,
    ).exclude(
        eventos__estado__in=(
            Evento.Estado.PROGRAMADO,
            Evento.Estado.FINALIZADO,
        )
    ).order_by("hora_inicio")
    ahora = timezone.localtime()
    turnos = [
        turno
        for turno in turnos_libres
        if fecha > ahora.date() or (fecha == ahora.date() and turno.hora_inicio > ahora.time())
    ]

    return {"precio_por_turno": precio, "turnos": turnos, "franjas": franjas}
