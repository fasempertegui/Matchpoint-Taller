from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario, UsuarioRol

from .fechas import (
    mes_siguiente, validar_fecha_alta, validar_mes_contratacion, validar_mes_contratacion_propia,
)
from .models import Membresia, MembresiaUsuario, Plan, PlanUsuario
from .servicios import exigir_administracion_membresias


def _bloquear_titular(actor, usuario_id, *, exigir_activo=True):
    exigir_administracion_membresias(actor)
    usuarios = {
        usuario.pk: usuario for usuario in Usuario.objects.select_for_update()
        .filter(pk__in=(actor.pk, usuario_id)).order_by("pk")
    }
    actor = exigir_administracion_membresias(actor)
    titular = usuarios.get(usuario_id)
    if titular is None or (exigir_activo and not titular.is_active):
        raise ValidationError("Elegí un usuario activo para registrar la contratación.")
    return actor, titular


class ContratacionExistente(ValidationError):
    def __init__(self, contratacion):
        self.contratacion = contratacion
        super().__init__("Ya existe una contratación de este tipo para el titular y mes elegidos. Podés consultarla.")


def _datos_revision(actor, titular, producto, mes_cubierto, referencia):
    return {
        "actor": actor.pk, "titular": titular.pk, "producto": producto.pk,
        "precio": str(producto.precio_vigente), "actualizado_en": producto.actualizado_en.isoformat(),
        "mes": mes_cubierto.isoformat() if mes_cubierto is not None else None,
        "referencia": referencia.pk if referencia is not None else None,
        "referencia_actualizada_en": referencia.actualizado_en.isoformat() if referencia is not None else None,
    }


def revision_precio_contratacion(actor, titular, producto, *, mes_cubierto=None, referencia=None):
    return signing.dumps(
        _datos_revision(actor, titular, producto, mes_cubierto, referencia),
        salt=f"membresias.precio_{producto._meta.model_name}",
    )


def _validar_revision_precio(actor, titular, producto, revision, *, mes_cubierto=None, referencia=None):
    try:
        datos = signing.loads(revision, salt=f"membresias.precio_{producto._meta.model_name}")
    except (signing.BadSignature, TypeError):
        raise ValidationError("La revisión del precio no es válida. Revisá el importe y volvé a confirmar.") from None
    if datos != _datos_revision(actor, titular, producto, mes_cubierto, referencia):
        raise ValidationError("La selección o sus condiciones cambiaron. Revisá los datos y volvé a confirmar.")


def _bloquear_titular_propio(actor):
    if actor is None or not actor.is_authenticated:
        raise PermissionDenied
    try:
        return Usuario.objects.select_for_update().get(
            pk=actor.pk, is_active=True, debe_cambiar_contrasena=False,
        )
    except Usuario.DoesNotExist:
        raise PermissionDenied from None


def _registrar_contratacion(
    actor, titular, *, modelo, producto_id, mes_cubierto, fecha_alta, revision_precio,
    observaciones="", propia=False, referencia_id=None,
):
    es_plan = modelo is PlanUsuario
    modelo_producto = Plan if es_plan else Membresia
    campo_producto = "plan" if es_plan else "membresia"
    if es_plan and titular.tiene_rol(Rol.PROFESOR):
        raise ValidationError("Un usuario con rol Profesor no puede contratar planes de clases.")
    if propia:
        validar_mes_contratacion_propia(mes_cubierto)
        fecha_alta = timezone.localdate()
    else:
        validar_mes_contratacion(mes_cubierto)
    validar_fecha_alta(fecha_alta)
    existente = modelo.objects.filter(usuario=titular, mes_cubierto=mes_cubierto).exclude(
        estado=modelo.Estado.ANULADO,
    ).first()
    if existente is not None:
        raise ContratacionExistente(existente)
    try:
        producto = modelo_producto.objects.select_for_update().get(pk=producto_id)
    except modelo_producto.DoesNotExist:
        raise ValidationError("El producto seleccionado ya no está disponible.") from None
    if producto.estado != modelo_producto.Estado.ACTIVO:
        raise ValidationError("Elegí un producto Activo para registrar la contratación.")
    referencia = None
    if propia and es_plan:
        if not titular.tiene_rol(Rol.ALUMNO):
            raise PermissionDenied
        referencia = PlanUsuario.objects.select_for_update().filter(
            pk=referencia_id, usuario=titular, plan=producto,
        ).exclude(estado=PlanUsuario.Estado.ANULADO).first()
        if referencia is None or mes_cubierto != mes_siguiente(referencia.mes_cubierto):
            raise ValidationError("La renovación requiere una contratación propia no Anulada del mismo plan para el mes anterior.")
    _validar_revision_precio(
        actor, titular, producto, revision_precio,
        mes_cubierto=mes_cubierto if propia else None, referencia=referencia,
    )
    contratacion = modelo(
        usuario=titular, **{campo_producto: producto}, mes_cubierto=mes_cubierto, fecha_alta=fecha_alta,
        precio_aplicado=producto.precio_vigente, registrado_por=actor, observaciones=observaciones.strip(),
        estado=modelo.Estado.VENCIDO if mes_cubierto < timezone.localdate().replace(day=1)
        else modelo.Estado.ACTIVO,
    )
    contratacion.full_clean()
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            contratacion.save()
            if es_plan and contratacion.estado == modelo.Estado.ACTIVO and not titular.tiene_rol(Rol.ADMINISTRADOR):
                UsuarioRol.objects.get_or_create(
                    usuario=titular, rol=Rol.objects.get(codigo=Rol.ALUMNO), defaults={"asignado_por": actor},
                )
    except IntegrityError as error:
        restriccion = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if restriccion == f"{campo_producto}_usuario_mes_no_anulado_unico":
            existente = modelo.objects.filter(usuario=titular, mes_cubierto=mes_cubierto).exclude(
                estado=modelo.Estado.ANULADO,
            ).get()
            raise ContratacionExistente(existente) from None
        raise
    return contratacion


@transaction.atomic
def registrar_contratacion_plan(
    actor, *, usuario_id, plan_id, mes_cubierto, fecha_alta, revision_precio, observaciones="",
):
    actor, titular = _bloquear_titular(actor, usuario_id)
    return _registrar_contratacion(
        actor, titular, modelo=PlanUsuario, producto_id=plan_id, mes_cubierto=mes_cubierto,
        fecha_alta=fecha_alta, revision_precio=revision_precio, observaciones=observaciones,
    )


@transaction.atomic
def registrar_contratacion_membresia(
    actor, *, usuario_id, membresia_id, mes_cubierto, fecha_alta, revision_precio, observaciones="",
):
    actor, titular = _bloquear_titular(actor, usuario_id)
    return _registrar_contratacion(
        actor, titular, modelo=MembresiaUsuario, producto_id=membresia_id, mes_cubierto=mes_cubierto,
        fecha_alta=fecha_alta, revision_precio=revision_precio, observaciones=observaciones,
    )


@transaction.atomic
def contratar_membresia_propia(actor, *, membresia_id, mes_cubierto, revision_precio, observaciones=""):
    titular = _bloquear_titular_propio(actor)
    return _registrar_contratacion(
        titular, titular, modelo=MembresiaUsuario, producto_id=membresia_id, mes_cubierto=mes_cubierto,
        fecha_alta=timezone.localdate(), revision_precio=revision_precio, observaciones=observaciones, propia=True,
    )


@transaction.atomic
def renovar_plan_propio(actor, *, referencia_id, mes_cubierto, revision_precio, observaciones=""):
    titular = _bloquear_titular_propio(actor)
    referencia = PlanUsuario.objects.filter(pk=referencia_id, usuario=titular).first()
    if referencia is None:
        raise ValidationError("Elegí una contratación propia para renovar el mismo plan.")
    return _registrar_contratacion(
        titular, titular, modelo=PlanUsuario, producto_id=referencia.plan_id, mes_cubierto=mes_cubierto,
        fecha_alta=timezone.localdate(), revision_precio=revision_precio, observaciones=observaciones, propia=True, referencia_id=referencia_id,
    )


def version_anulacion_contratacion(actor, contratacion, *, tipo):
    return signing.dumps({
        "actor": actor.pk, "contratacion": contratacion.pk,
        "actualizado_en": contratacion.actualizado_en.isoformat(),
    }, salt=f"membresias.anular_{tipo}")


@transaction.atomic
def _anular_contratacion(actor, contratacion_id, *, modelo, tipo, motivo, version):
    exigir_administracion_membresias(actor)
    titular_id = modelo.objects.values_list("usuario_id", flat=True).get(pk=contratacion_id)
    actor, _ = _bloquear_titular(actor, titular_id, exigir_activo=False)
    contratacion = modelo.objects.select_for_update().get(pk=contratacion_id)
    if contratacion.estado == modelo.Estado.ANULADO:
        return contratacion
    if contratacion.estado != modelo.Estado.ACTIVO:
        raise ValidationError("Sólo se pueden anular contrataciones Activas.")
    try:
        datos = signing.loads(version, salt=f"membresias.anular_{tipo}")
    except (signing.BadSignature, TypeError):
        raise ValidationError("La revisión no es válida. Volvé a abrir la anulación antes de confirmar.") from None
    if datos != {
        "actor": actor.pk, "contratacion": contratacion.pk,
        "actualizado_en": contratacion.actualizado_en.isoformat(),
    }:
        raise ValidationError("La contratación cambió. Volvé a revisar sus datos antes de confirmar la anulación.")
    motivo = motivo.strip()
    if not motivo:
        raise ValidationError("Indicá el motivo de la anulación.")
    contratacion.estado = modelo.Estado.ANULADO
    contratacion.motivo_anulacion = motivo
    contratacion.anulado_por = actor
    contratacion.anulado_en = timezone.now()
    contratacion.full_clean()
    with contexto_auditoria(actor):
        contratacion.save(update_fields=[
            "estado", "motivo_anulacion", "anulado_por", "anulado_en", "actualizado_en",
        ])
    return contratacion


def anular_contratacion_plan(actor, contratacion_id, *, motivo, version):
    return _anular_contratacion(
        actor, contratacion_id, modelo=PlanUsuario, tipo="plan", motivo=motivo, version=version,
    )


def anular_contratacion_membresia(actor, contratacion_id, *, motivo, version):
    return _anular_contratacion(
        actor, contratacion_id, modelo=MembresiaUsuario, tipo="membresia", motivo=motivo, version=version,
    )


def validar_retiro_rol_alumno(usuario):
    if PlanUsuario.objects.filter(usuario=usuario, estado=PlanUsuario.Estado.ACTIVO).exists():
        raise ValidationError("No se puede quitar el rol Alumno mientras el usuario tenga contrataciones de planes Activas.")


def vencer_contrataciones():
    procesado_en = timezone.now()
    inicio_mes_actual = timezone.localtime(procesado_en).date().replace(day=1)
    cantidades = {}
    with contexto_auditoria(origen="tarea"):
        for tipo, modelo in (("planes", PlanUsuario), ("membresias", MembresiaUsuario)):
            cantidades[tipo] = modelo.objects.filter(
                estado=modelo.Estado.ACTIVO, mes_cubierto__lt=inicio_mes_actual,
            ).update(estado=modelo.Estado.VENCIDO, actualizado_en=procesado_en)
    return cantidades
