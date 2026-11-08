from uuid import UUID

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios

from .ingresos import ORIGENES, consultar_origen, origen_del_movimiento
from .finanzas import situacion_financiera, validar_revision_devolucion
from .models import MovimientoFondo, SesionCaja
from .servicios import efectivo_esperado, exigir_acceso_caja


def _reintento(movimiento, datos):
    if any(getattr(movimiento, campo) != valor for campo, valor in datos.items()):
        raise ValidationError("Este identificador ya se usó con otros datos. Iniciá un nuevo movimiento.")
    return movimiento


@transaction.atomic
def registrar_movimiento(actor, sesion_id, *, clase, operacion_id, concepto, monto, medio_pago,
                         categoria_ingreso="", categoria_egreso="", destinatario="", referencia="",
                         verificado=False, tipo_origen="general", origen_id=None, revision_devolucion=None):
    actor = exigir_acceso_caja(actor)
    try:
        operacion = UUID(str(operacion_id))
        sesion_id = int(sesion_id)
        origen_id = int(origen_id) if origen_id is not None else None
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Revisá la sesión, el origen y el identificador de operación.") from None
    if clase not in MovimientoFondo.Clase.values:
        raise ValidationError("Elegí una clase de movimiento válida.")
    if tipo_origen != "general" and tipo_origen not in ORIGENES:
        raise ValidationError("Elegí un tipo de origen válido.")
    es_devolucion = clase == "egreso" and categoria_egreso == "devoluciones"
    if (tipo_origen == "general") != (origen_id is None) or (clase != "ingreso" and not es_devolucion and tipo_origen != "general"):
        raise ValidationError("Sólo los ingresos y las devoluciones admiten un vínculo comercial, como máximo uno.")
    if revision_devolucion is not None and not es_devolucion:
        raise ValidationError("La revisión corresponde únicamente a una devolución.")
    if clase == MovimientoFondo.Clase.INGRESO:
        categoria_esperada = ORIGENES[tipo_origen][2] if tipo_origen != "general" else MovimientoFondo.CategoriaIngreso.OTROS
        if categoria_ingreso and categoria_ingreso != categoria_esperada:
            raise ValidationError("La categoría del ingreso debe corresponder al origen. Los ingresos sin vínculo se registran como Otros.")
        categoria_ingreso = categoria_esperada
    if isinstance(monto, float):
        raise ValidationError("El monto debe tener hasta dos decimales.")
    monto = MovimientoFondo._meta.get_field("monto").clean(monto, None)
    if medio_pago not in MovimientoFondo.Medio.values:
        raise ValidationError("Elegí un medio de pago válido.")
    if clase in ("aporte", "retiro") and medio_pago != "efectivo":
        raise ValidationError("Los aportes y retiros se registran únicamente en efectivo.")
    if medio_pago != "efectivo" and (verificado is not True or not referencia.strip()):
        raise ValidationError("Indicá una referencia y verificá manualmente el pago.")
    datos = {
        "sesion_id": sesion_id, "registrado_por_id": actor.pk, "clase": clase,
        "concepto": concepto.strip(), "monto": monto, "medio_pago": medio_pago,
        "referencia": referencia.strip(), "categoria_ingreso": categoria_ingreso,
        "categoria_egreso": categoria_egreso, "destinatario": destinatario.strip(),
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
        raise ValidationError("La sesión está cerrada. No admite nuevos movimientos.")
    if origen:
        origen = consultar_origen(tipo_origen, origen_id, bloquear=True)
        anulado = origen.evento.estado == "anulado" if tipo_origen == "reserva" else origen.estado == "anulado"
        if anulado and clase == "ingreso":
            raise ValidationError("El origen está Anulado y no admite nuevos cobros.")
    movimiento = MovimientoFondo(operacion_id=operacion, **datos)
    movimiento.full_clean(validate_unique=False)
    if es_devolucion:
        situacion = situacion_financiera(tipo_origen, origen_id) if origen else None
        if situacion is not None and monto > situacion["maximo_devolucion"]:
            raise ValidationError(f"El máximo disponible para devolver es ARS {situacion['maximo_devolucion']:.2f}.")
        if revision_devolucion is not None:
            revisados = {**datos, "operacion_id": operacion, "verificado": verificado}
            validar_revision_devolucion(actor, sesion_id, tipo_origen, origen_id, revisados, situacion, revision_devolucion)
    if efectivo_esperado(sesion) + movimiento.efecto_efectivo < 0:
        raise ValidationError("El efectivo disponible no alcanza para esta salida.")
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            movimiento.save()
    except IntegrityError:
        anterior = MovimientoFondo.objects.filter(operacion_id=operacion).first()
        if anterior is None:
            raise
        return _reintento(anterior, datos)
    return movimiento


def revision_anulacion(actor, movimiento, sesion_actual):
    return signing.dumps({
        "actor": actor.pk, "movimiento": movimiento.pk, "operacion": str(movimiento.operacion_id),
        "sesion_actual": sesion_actual.pk,
    }, salt="caja.anulacion")


@transaction.atomic
def anular_movimiento(actor, movimiento_id, *, motivo, revision):
    actor = exigir_acceso_caja(actor)
    actual = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
    if actual is None:
        raise PermissionDenied
    try:
        inicial = MovimientoFondo.objects.get(pk=movimiento_id)
    except MovimientoFondo.DoesNotExist:
        raise ValidationError("El movimiento no existe.") from None
    tipo_comercial, origen_id = origen_del_movimiento(inicial)
    comercial = consultar_origen(tipo_comercial, origen_id) if origen_id is not None else None
    titular_id = comercial.organizador_id if tipo_comercial == "reserva" else comercial.usuario_id if comercial else None
    bloquear_usuarios({actor.pk} | ({titular_id} if titular_id else set()))
    actor = exigir_acceso_caja(actor)
    sesiones = {s.pk: s for s in SesionCaja.objects.select_for_update().filter(pk__in={actual.pk, inicial.sesion_id}).order_by("pk")}
    actual = sesiones[actual.pk]
    if actual.estado != "abierta" or actual.responsable_id != actor.pk:
        raise ValidationError("La sesión actual cambió. Revisá nuevamente antes de anular.")
    if comercial is not None:
        consultar_origen(tipo_comercial, origen_id, bloquear=True)
    movimiento = MovimientoFondo.objects.select_for_update().get(pk=movimiento_id)
    if movimiento.estado != "vigente":
        raise ValidationError("El movimiento ya está Anulado y no admite otra anulación.")
    try:
        datos = signing.loads(revision, salt="caja.anulacion", max_age=900)
    except (signing.BadSignature, TypeError):
        raise ValidationError("La revisión de anulación venció o no es válida. Revisá nuevamente.") from None
    if datos != {"actor": actor.pk, "movimiento": movimiento.pk, "operacion": str(movimiento.operacion_id), "sesion_actual": actual.pk}:
        raise ValidationError("Cambió la sesión o el movimiento. Revisá nuevamente antes de anular.")
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError("Explicá el motivo de anulación.")
    origen = sesiones[movimiento.sesion_id]
    if origen.estado == "abierta" and efectivo_esperado(origen) - movimiento.efecto_efectivo < 0:
        raise ValidationError("Anular este movimiento dejaría el efectivo esperado negativo.")
    movimiento.estado = "anulado"
    movimiento.anulado_por = actor
    movimiento.anulado_en = timezone.now()
    movimiento.motivo_anulacion = motivo
    movimiento.full_clean()
    with contexto_auditoria(actor):
        movimiento.save(update_fields=["estado", "anulado_por", "anulado_en", "motivo_anulacion"])
    return movimiento
