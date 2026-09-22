import datetime as dt

from django.core.exceptions import ValidationError
from django.utils import timezone


def _sumar_anios(fecha, cantidad):
    try:
        return fecha.replace(year=fecha.year + cantidad)
    except ValueError:
        # 29 de febrero en un año no bisiesto.
        return fecha.replace(year=fecha.year + cantidad, day=28)


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
