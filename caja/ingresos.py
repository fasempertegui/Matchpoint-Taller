from uuid import UUID

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios
from membresias.models import PlanUsuario, MembresiaUsuario
from reservas.models import Reserva, Evento

from .models import MovimientoFondo, SesionCaja
from .servicios import exigir_acceso_caja


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


def _reintento(movimiento, datos):
    if any(getattr(movimiento, campo) != valor for campo, valor in datos.items()):
        raise ValidationError("Este identificador ya se usó con otros datos. Iniciá un nuevo ingreso.")
    return movimiento


@transaction.atomic
def registrar_ingreso(actor, sesion_id, *, operacion_id, concepto, monto, medio_pago,
                      categoria_ingreso="", referencia="", verificado=False, tipo_origen="general", origen_id=None):
    actor = exigir_acceso_caja(actor)
    try:
        operacion = UUID(str(operacion_id))
        sesion_id = int(sesion_id)
        origen_id = int(origen_id) if origen_id is not None else None
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Revisá la sesión, el origen y el identificador de operación.") from None
    if tipo_origen != "general" and tipo_origen not in ORIGENES:
        raise ValidationError("Elegí un tipo de origen válido.")
    if (tipo_origen == "general") != (origen_id is None):
        raise ValidationError("Revisá el vínculo del ingreso.")
    if isinstance(monto, float):
        raise ValidationError("El monto debe tener hasta dos decimales.")
    monto = MovimientoFondo._meta.get_field("monto").clean(monto, None)
    if medio_pago not in MovimientoFondo.Medio.values:
        raise ValidationError("Elegí un medio de pago válido.")
    if medio_pago != "efectivo" and (verificado is not True or not referencia.strip()):
        raise ValidationError("Indicá una referencia y verificá manualmente la recepción o aprobación del pago.")
    datos = {
        "sesion_id": sesion_id, "registrado_por_id": actor.pk, "clase": "ingreso",
        "concepto": concepto.strip(), "monto": monto, "medio_pago": medio_pago,
        "referencia": referencia.strip(), "categoria_ingreso": ORIGENES[tipo_origen][2] if tipo_origen != "general" else categoria_ingreso,
        "plan_usuario_id": None, "membresia_usuario_id": None, "reserva_id": None,
    }
    if tipo_origen != "general":
        datos[ORIGENES[tipo_origen][1]] = origen_id
    anterior = MovimientoFondo.objects.filter(operacion_id=operacion).first()
    if anterior:
        exigir_acceso_caja(actor, bloquear=True)
        return _reintento(anterior, datos)
    origen = consultar_origen(tipo_origen, origen_id) if tipo_origen != "general" else None
    titular_id = origen.organizador_id if tipo_origen == "reserva" else origen.usuario_id if origen else None
    bloquear_usuarios({actor.pk} | ({titular_id} if titular_id else set()))
    actor = exigir_acceso_caja(actor)
    try:
        sesion = SesionCaja.objects.select_for_update().get(pk=sesion_id)
    except SesionCaja.DoesNotExist:
        raise ValidationError("La sesión de caja no existe.") from None
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    anterior = MovimientoFondo.objects.filter(operacion_id=operacion).first()
    if anterior:
        return _reintento(anterior, datos)
    if sesion.estado != SesionCaja.Estado.ABIERTA:
        raise ValidationError("La sesión está cerrada. No se pueden registrar nuevos ingresos.")
    if origen:
        origen = consultar_origen(tipo_origen, origen_id, bloquear=True)
        anulado = origen.evento.estado == Evento.Estado.ANULADO if tipo_origen == "reserva" else origen.estado == "anulado"
        if anulado:
            raise ValidationError("El origen está Anulado y no admite nuevos cobros.")
    movimiento = MovimientoFondo(operacion_id=operacion, **datos)
    movimiento.full_clean(validate_unique=False)
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            movimiento.save()
    except IntegrityError:
        anterior = MovimientoFondo.objects.filter(operacion_id=operacion).first()
        if anterior is None:
            raise
        return _reintento(anterior, datos)
    return movimiento
