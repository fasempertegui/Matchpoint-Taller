from django.core.exceptions import ValidationError

from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.models import Reserva

from .models import MovimientoFondo


ORIGENES = {
    "plan": (PlanUsuario, "plan_usuario_id", "planes"),
    "membresia": (MembresiaUsuario, "membresia_usuario_id", "membresias"),
    "reserva": (Reserva, "reserva_id", "reservas"),
}


def consultar_origen(tipo, origen_id, *, bloquear=False):
    if tipo not in ORIGENES:
        raise ValidationError("Elegí un tipo de origen válido.")
    modelo = ORIGENES[tipo][0]
    consulta = modelo.objects.all()
    consulta = consulta.select_related("organizador", "evento__turno__cancha__sede") if tipo == "reserva" else consulta.select_related("usuario", "plan" if tipo == "plan" else "membresia")
    if bloquear:
        consulta = consulta.select_for_update(of=("self",))
    try:
        return consulta.get(pk=origen_id)
    except (modelo.DoesNotExist, ValueError, TypeError):
        raise ValidationError("El origen seleccionado no existe.") from None


def cobros_del_origen(tipo, origen_id):
    return MovimientoFondo.objects.filter(**{ORIGENES[tipo][1]: origen_id}, clase="ingreso", estado="vigente")


def registrar_ingreso(actor, sesion_id, **datos):
    from .movimientos import registrar_movimiento
    return registrar_movimiento(actor, sesion_id, clase="ingreso", **datos)
