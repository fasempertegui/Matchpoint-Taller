from calendar import monthrange
from dataclasses import dataclass
from datetime import time

from clases.models import Feriado

from .models import SedeHorarioEspecial


@dataclass(frozen=True)
class HorarioEfectivo:
    franjas: tuple[tuple[time, time], ...]
    especial: SedeHorarioEspecial | None
    feriado: Feriado | None

    def contiene(self, inicio, fin):
        return any(apertura <= inicio < fin <= cierre for apertura, cierre in self.franjas)


def franjas_horario(horario):
    if horario is None or horario.hora_inicio_1 is None:
        return ()
    primera = (horario.hora_inicio_1, horario.hora_fin_1)
    if horario.hora_inicio_2 is None:
        return (primera,)
    return (primera, (horario.hora_inicio_2, horario.hora_fin_2))


def horarios_efectivos(sede, fechas):
    fechas = set(fechas)
    habituales = {
        horario.dia_semana: horario
        for horario in sede.horarios.filter(dia_semana__in={fecha.isoweekday() for fecha in fechas})
    }
    especiales = {
        horario.fecha: horario
        for horario in sede.horarios_especiales.filter(fecha__in=fechas)
    }
    feriados = {
        feriado.fecha: feriado
        for feriado in Feriado.objects.filter(fecha__in=fechas)
    }
    return {
        fecha: HorarioEfectivo(
            franjas=franjas_horario(especiales.get(fecha) or habituales.get(fecha.isoweekday())),
            especial=especiales.get(fecha),
            feriado=feriados.get(fecha),
        )
        for fecha in fechas
    }


def horario_efectivo(sede, fecha):
    return horarios_efectivos(sede, (fecha,))[fecha]


def horarios_del_mes(sede, mes):
    ultimo_dia = monthrange(mes.year, mes.month)[1]
    return horarios_efectivos(sede, (mes.replace(day=dia) for dia in range(1, ultimo_dia + 1)))
