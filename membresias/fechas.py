from datetime import date

from django.core.exceptions import ValidationError
from django.utils import timezone

from common.fechas import FECHA_INICIO_OPERACIONES


def mes_siguiente(fecha):
    return date(fecha.year + fecha.month // 12, fecha.month % 12 + 1, 1)


def meses_contratables(*, incluir_mes_siguiente=False):
    mes = FECHA_INICIO_OPERACIONES
    hoy = timezone.localdate()
    limite = mes_siguiente(hoy) if incluir_mes_siguiente or hoy.day >= 25 else hoy.replace(day=1)
    meses = []
    while mes <= limite:
        meses.append(mes)
        mes = mes_siguiente(mes)
    return meses


def validar_mes_contratacion(mes):
    if mes not in meses_contratables():
        raise ValidationError(
            "Elegí un mes desde agosto de 2026 hasta el actual. "
            "El mes siguiente se habilita desde el día 25 inclusive."
        )


def validar_fecha_alta(fecha):
    if not FECHA_INICIO_OPERACIONES <= fecha <= timezone.localdate():
        raise ValidationError("La fecha efectiva de alta debe estar entre el 01/08/2026 y hoy.")
