from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario

from .models import Pase, Plan


def exigir_administracion_membresias(usuario, *, bloquear=False):
    if usuario is None or not usuario.is_authenticated:
        raise PermissionDenied
    usuarios = Usuario.objects.all()
    if bloquear:
        usuarios = usuarios.select_for_update()
    try:
        usuario = usuarios.get(pk=usuario.pk, is_active=True, debe_cambiar_contrasena=False)
    except Usuario.DoesNotExist:
        raise PermissionDenied from None
    if not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    return usuario


def version_producto(usuario, producto):
    return signing.dumps({
        "usuario": usuario.pk, "producto": producto.pk, "actualizado_en": producto.actualizado_en.isoformat(),
    }, salt=f"membresias.{producto._meta.model_name}")


def _validar_version_producto(usuario, producto, version):
    nombre_tipo = producto._meta.verbose_name
    try:
        datos = signing.loads(version, salt=f"membresias.{producto._meta.model_name}")
    except (signing.BadSignature, TypeError):
        raise ValidationError(f"La selección no es válida. Volvé a abrir el {nombre_tipo} antes de confirmar.") from None
    if datos != {"usuario": usuario.pk, "producto": producto.pk, "actualizado_en": producto.actualizado_en.isoformat()}:
        raise ValidationError(f"El {nombre_tipo} cambió. Volvé a abrirlo para revisar sus datos antes de confirmar.")


def _guardar_producto(producto, campos=None):
    producto.full_clean()
    try:
        with transaction.atomic():
            producto.save(update_fields=campos)
    except IntegrityError as error:
        restriccion = f"{producto._meta.model_name}_nombre_activo_unico"
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == restriccion:
            raise ValidationError(f"Ya existe un {producto._meta.verbose_name} activo con ese nombre.") from None
        raise


@transaction.atomic
def guardar_plan(
    usuario, *, nombre, descripcion, modalidad, frecuencia_semanal,
    cantidad_clases_por_encuentro, precio_vigente, plan_id=None, version="",
):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    plan = Plan.objects.select_for_update().get(pk=plan_id) if plan_id is not None else Plan()
    if plan_id is not None:
        _validar_version_producto(usuario, plan, version)
    datos = {
        "nombre": nombre.strip(), "descripcion": descripcion.strip(), "modalidad": modalidad,
        "frecuencia_semanal": frecuencia_semanal,
        "cantidad_clases_por_encuentro": cantidad_clases_por_encuentro, "precio_vigente": precio_vigente,
    }
    cambios = [campo for campo, valor in datos.items() if getattr(plan, campo) != valor]
    for campo, valor in datos.items():
        setattr(plan, campo, valor)
    if plan_id is not None and not cambios:
        return plan
    with contexto_auditoria(usuario):
        _guardar_producto(plan, campos=cambios + ["actualizado_en"] if plan_id is not None else None)
    return plan


@transaction.atomic
def cambiar_estado_plan(usuario, plan_id, estado, *, version):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    plan = Plan.objects.select_for_update().get(pk=plan_id)
    if estado not in Plan.Estado.values:
        raise ValidationError("Elegí un estado válido para el plan.")
    if plan.estado == estado:
        return plan
    _validar_version_producto(usuario, plan, version)
    plan.estado = estado
    with contexto_auditoria(usuario):
        _guardar_producto(plan, campos=["estado", "actualizado_en"])
    return plan


@transaction.atomic
def guardar_pase(
    usuario, *, nombre, descripcion, tipo, limite_horas_diarias, precio_vigente,
    precio_invitado_vigente, pase_id=None, version="",
):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    pase = Pase.objects.select_for_update().get(pk=pase_id) if pase_id is not None else Pase()
    if pase_id is not None:
        _validar_version_producto(usuario, pase, version)
    datos = {
        "nombre": nombre.strip(), "descripcion": descripcion.strip(), "tipo": tipo,
        "limite_horas_diarias": limite_horas_diarias, "precio_vigente": precio_vigente,
        "precio_invitado_vigente": precio_invitado_vigente,
    }
    cambios = [campo for campo, valor in datos.items() if getattr(pase, campo) != valor]
    for campo, valor in datos.items():
        setattr(pase, campo, valor)
    if pase_id is not None and not cambios:
        return pase
    with contexto_auditoria(usuario):
        _guardar_producto(pase, campos=cambios + ["actualizado_en"] if pase_id is not None else None)
    return pase


@transaction.atomic
def cambiar_estado_pase(usuario, pase_id, estado, *, version):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    pase = Pase.objects.select_for_update().get(pk=pase_id)
    if estado not in Pase.Estado.values:
        raise ValidationError("Elegí un estado válido para el pase.")
    if pase.estado == estado:
        return pase
    _validar_version_producto(usuario, pase, version)
    pase.estado = estado
    with contexto_auditoria(usuario):
        _guardar_producto(pase, campos=["estado", "actualizado_en"])
    return pase
