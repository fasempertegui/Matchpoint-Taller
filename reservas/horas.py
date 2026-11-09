from django.db.models import Q, Sum
from django.utils import timezone

from membresias.models import AjusteHorasMembresia

from .models import Evento, Reserva, ReservaInvitado


def usos_del_mes(usuario_id, mes):
    return Reserva.objects.filter(
        organizador_id=usuario_id, computa_hora_membresia=True,
        evento__turno__fecha__year=mes.year, evento__turno__fecha__month=mes.month,
    )


def usos_invitado_del_mes(usuario_id, mes):
    return ReservaInvitado.objects.filter(
        usuario_id=usuario_id, condicion_aplicada="socio",
        respuesta__in=("pendiente", "afirmativa"), reserva__membresia_usuario__isnull=False,
        reserva__evento__turno__fecha__year=mes.year, reserva__evento__turno__fecha__month=mes.month,
    ).exclude(reserva__evento__estado=Evento.Estado.ANULADO)


def _saldo_horas(contrato, tipo_horas, usadas):
    cupo = getattr(contrato, f"horas_{tipo_horas}_aplicadas") if contrato else 0
    totales = {"otorgadas": 0, "descontadas": 0}
    if contrato:
        totales = contrato.ajustes_horas.filter(tipo_horas=tipo_horas).aggregate(
            otorgadas=Sum("cantidad", filter=Q(operacion="otorgar"), default=0),
            descontadas=Sum("cantidad", filter=Q(operacion="quitar"), default=0),
        )
    saldo = cupo + totales["otorgadas"] - totales["descontadas"] - usadas
    return {"cupo": cupo, **totales, "saldo": saldo, "disponibles": max(0, saldo)}


def saldo_horas_contratacion(contrato, tipo_horas):
    if tipo_horas not in AjusteHorasMembresia.TipoHoras.values:
        raise ValueError("El tipo de horas no es válido.")
    consulta = usos_del_mes if tipo_horas == "organizador" else usos_invitado_del_mes
    usadas = consulta(contrato.usuario_id, contrato.mes_cubierto).count()
    return _saldo_horas(contrato, tipo_horas, usadas)


def horas_disponibles_invitado(contrato):
    return saldo_horas_contratacion(contrato, "invitado")["disponibles"]


def horas_disponibles_organizador(contrato):
    return saldo_horas_contratacion(contrato, "organizador")["disponibles"]


def resumen_horas_del_mes(usuario_id, mes, contrato):
    organizador = usos_del_mes(usuario_id, mes)
    invitados = usos_invitado_del_mes(usuario_id, mes)
    ahora = timezone.localtime()
    inicio_alcanzado = Q(reserva__evento__turno__fecha__lt=ahora.date()) | Q(
        reserva__evento__turno__fecha=ahora.date(), reserva__evento__turno__hora_inicio__lte=ahora.time(),
    )
    filas = []
    for rol, tipo_horas, comprometidas, consumidas in (
        ("Organizador", "organizador",
         organizador.filter(evento__estado=Evento.Estado.PROGRAMADO).count(),
         organizador.exclude(evento__estado=Evento.Estado.PROGRAMADO).count()),
        ("Invitado", "invitado",
         invitados.exclude(inicio_alcanzado).count(), invitados.filter(inicio_alcanzado).count()),
    ):
        filas.append({
            "mes": mes, "rol": rol, "tipo_horas": tipo_horas,
            **_saldo_horas(contrato, tipo_horas, comprometidas + consumidas),
            "comprometidas": comprometidas, "consumidas": consumidas,
        })
    return filas
