from datetime import date

from django.core.exceptions import ValidationError
from django.utils import timezone

from common.fechas import FECHA_INICIO_OPERACIONES


def mes_siguiente(fecha):
    return date(fecha.year + fecha.month // 12, fecha.month % 12 + 1, 1)


def meses_contratables():
    mes = FECHA_INICIO_OPERACIONES
    limite = mes_siguiente(timezone.localdate())
    meses = []
    while mes <= limite:
        meses.append(mes)
        mes = mes_siguiente(mes)
    return meses


def validar_mes_contratacion(mes):
    if mes.day != 1 or not FECHA_INICIO_OPERACIONES <= mes <= mes_siguiente(timezone.localdate()):
        raise ValidationError("Elegí un mes desde agosto de 2026 hasta el mes siguiente al actual.")


def validar_fecha_alta(fecha):
    if not FECHA_INICIO_OPERACIONES <= fecha <= timezone.localdate():
        raise ValidationError("La fecha efectiva de alta debe estar entre el 01/08/2026 y hoy.")
