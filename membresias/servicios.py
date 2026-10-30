from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario

from .models import Plan


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


def version_plan(usuario, plan):
    return signing.dumps({
        "usuario": usuario.pk, "plan": plan.pk, "actualizado_en": plan.actualizado_en.isoformat(),
    }, salt="membresias.plan")


def _validar_version_plan(usuario, plan, version):
    try:
        datos = signing.loads(version, salt="membresias.plan")
    except (signing.BadSignature, TypeError):
        raise ValidationError("La selección no es válida. Volvé a abrir el plan antes de confirmar.") from None
    if datos != {"usuario": usuario.pk, "plan": plan.pk, "actualizado_en": plan.actualizado_en.isoformat()}:
        raise ValidationError("El plan cambió. Volvé a abrirlo para revisar sus datos antes de confirmar.")


def _guardar_plan(plan, campos=None):
    plan.full_clean()
    try:
        with transaction.atomic():
            plan.save(update_fields=campos)
    except IntegrityError as error:
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == "plan_nombre_activo_unico":
            raise ValidationError("Ya existe un plan activo con ese nombre.") from None
        raise


@transaction.atomic
def guardar_plan(
    usuario, *, nombre, descripcion, modalidad, frecuencia_semanal,
    cantidad_clases_por_encuentro, precio_vigente, plan_id=None, version="",
):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    plan = Plan.objects.select_for_update().get(pk=plan_id) if plan_id is not None else Plan()
    if plan_id is not None:
        _validar_version_plan(usuario, plan, version)
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
        _guardar_plan(plan, campos=cambios + ["actualizado_en"] if plan_id is not None else None)
    return plan


@transaction.atomic
def cambiar_estado_plan(usuario, plan_id, estado, *, version):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    plan = Plan.objects.select_for_update().get(pk=plan_id)
    if estado not in Plan.Estado.values:
        raise ValidationError("Elegí un estado válido para el plan.")
    if plan.estado == estado:
        return plan
    _validar_version_plan(usuario, plan, version)
    plan.estado = estado
    with contexto_auditoria(usuario):
        _guardar_plan(plan, campos=["estado", "actualizado_en"])
    return plan
