from django.db.models import Q
from django.utils import timezone

from .models import Evento, Reserva, ReservaInvitado


def usos_del_mes(usuario_id, mes):
    return Reserva.objects.filter(
        organizador_id=usuario_id, computa_hora_membresia=True,
        evento__turno__fecha__year=mes.year, evento__turno__fecha__month=mes.month,
    )


def usos_invitado_del_mes(usuario_id, mes):
    return ReservaInvitado.objects.filter(
        usuario_id=usuario_id, condicion_aplicada="socio", estado="vigente",
        respuesta__in=("pendiente", "afirmativa"), reserva__membresia_usuario__isnull=False,
        reserva__evento__turno__fecha__year=mes.year, reserva__evento__turno__fecha__month=mes.month,
    ).exclude(reserva__evento__estado=Evento.Estado.ANULADO)


def horas_disponibles_invitado(contrato):
    usadas = usos_invitado_del_mes(contrato.usuario_id, contrato.mes_cubierto).count()
    return max(0, contrato.horas_invitado_aplicadas - usadas)


def resumen_horas_del_mes(usuario_id, mes, contrato):
    organizador = usos_del_mes(usuario_id, mes)
    invitados = usos_invitado_del_mes(usuario_id, mes)
    ahora = timezone.localtime()
    inicio_alcanzado = Q(reserva__evento__turno__fecha__lt=ahora.date()) | Q(
        reserva__evento__turno__fecha=ahora.date(), reserva__evento__turno__hora_inicio__lte=ahora.time(),
    )
    filas = []
    for rol, cupo, comprometidas, consumidas in (
        ("Organizador", contrato.horas_organizador_aplicadas if contrato else 0,
         organizador.filter(evento__estado=Evento.Estado.PROGRAMADO).count(),
         organizador.exclude(evento__estado=Evento.Estado.PROGRAMADO).count()),
        ("Invitado", contrato.horas_invitado_aplicadas if contrato else 0,
         invitados.exclude(inicio_alcanzado).count(), invitados.filter(inicio_alcanzado).count()),
    ):
        filas.append({
            "mes": mes, "rol": rol, "cupo": cupo, "comprometidas": comprometidas,
            "consumidas": consumidas, "disponibles": max(0, cupo - comprometidas - consumidas),
        })
    return filas
