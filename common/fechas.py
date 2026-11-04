import datetime as dt
from calendar import monthrange

from django.core.exceptions import ValidationError
from django.utils import formats, timezone


FECHA_INICIO_OPERACIONES = dt.date(2026, 8, 1)


def _sumar_anios(fecha, cantidad):
    try:
        return fecha.replace(year=fecha.year + cantidad)
    except ValueError:
        # 29 de febrero en un año no bisiesto.
        return fecha.replace(year=fecha.year + cantidad, day=28)


def fecha_maxima_agenda():
    return _sumar_anios(timezone.localdate(), 1)


def fecha_maxima_eventos():
    hoy = timezone.localdate()
    mes = hoy.month + 2
    anio = hoy.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return dt.date(anio, mes, monthrange(anio, mes)[1])


def fecha_maxima_feriados():
    return _sumar_anios(timezone.localdate(), 5)


def fecha_minima_nacimiento():
    return _sumar_anios(timezone.localdate(), -120)


def validar_fecha_nacimiento(fecha):
    hoy = timezone.localdate()
    if fecha > hoy:
        raise ValidationError("La fecha de nacimiento no puede ser futura.")
    minima = fecha_minima_nacimiento()
    if fecha < minima:
        raise ValidationError(
            f"La fecha de nacimiento no puede ser anterior al {minima:%d/%m/%Y}."
        )


def validar_inicio_evento(fecha, hora_inicio):
    maxima = fecha_maxima_eventos()
    if fecha > maxima:
        raise ValidationError(f"Sólo se pueden crear eventos hasta el {maxima:%d/%m/%Y}, inclusive.")
    inicio = timezone.make_aware(dt.datetime.combine(fecha, hora_inicio))
    if inicio <= timezone.now():
        raise ValidationError("El evento debe comenzar en un horario futuro. El turno ya comenzó.")


def opciones_meses_agenda():
    mes = max(FECHA_INICIO_OPERACIONES, timezone.localdate().replace(day=1))
    maxima = fecha_maxima_eventos()
    opciones = []
    while mes.replace(day=monthrange(mes.year, mes.month)[1]) <= maxima:
        nombre = formats.date_format(mes, "F").capitalize()
        opciones.append((mes.strftime("%Y-%m"), f"{nombre} de {mes.year}"))
        mes = dt.date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)
    return opciones
