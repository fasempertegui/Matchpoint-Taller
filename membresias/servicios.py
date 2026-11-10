from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario

from .models import Membresia, Plan


def exigir_administracion_membresias(usuario, *, bloquear=False):
    if usuario is None or not usuario.is_authenticated:
        raise PermissionDenied
    usuarios = Usuario.objects.all()
    if bloquear:
        usuarios = usuarios.select_for_update()
    try:
        usuario = usuarios.get(pk=usuario.pk, is_active=True, correo_verificado_en__isnull=False, debe_cambiar_contrasena=False)
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
    articulo = "la" if isinstance(producto, Membresia) else "el"
    try:
        datos = signing.loads(version, salt=f"membresias.{producto._meta.model_name}")
    except (signing.BadSignature, TypeError):
        raise ValidationError(f"La selección no es válida. Volvé a abrir {articulo} {nombre_tipo} antes de confirmar.") from None
    if datos != {"usuario": usuario.pk, "producto": producto.pk, "actualizado_en": producto.actualizado_en.isoformat()}:
        raise ValidationError(f"{articulo.capitalize()} {nombre_tipo} cambió. Volvé a abrir el registro para revisar sus datos antes de confirmar.")


def _guardar_producto(producto, campos=None):
    producto.full_clean()
    try:
        with transaction.atomic():
            producto.save(update_fields=campos)
    except IntegrityError as error:
        restriccion = f"{producto._meta.model_name}_nombre_activo_unico"
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == restriccion:
            mensaje = "Ya existe una membresía activa con ese nombre." if isinstance(producto, Membresia) else "Ya existe un plan activo con ese nombre."
            raise ValidationError(mensaje) from None
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
    estructura = {"modalidad", "frecuencia_semanal", "cantidad_clases_por_encuentro"}
    if plan_id is not None and estructura.intersection(cambios) and plan.contrataciones.exists():
        raise ValidationError("La modalidad, frecuencia y duración no se pueden cambiar en un plan con contrataciones.")
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
def guardar_membresia(
    usuario, *, nombre, descripcion, horas_organizador, horas_invitado, precio_vigente,
    precio_invitado_vigente, membresia_id=None, version="",
):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    membresia = Membresia.objects.select_for_update().get(pk=membresia_id) if membresia_id is not None else Membresia()
    if membresia_id is not None:
        _validar_version_producto(usuario, membresia, version)
    datos = {
        "nombre": nombre.strip(), "descripcion": descripcion.strip(),
        "horas_organizador": horas_organizador, "horas_invitado": horas_invitado,
        "precio_vigente": precio_vigente, "precio_invitado_vigente": precio_invitado_vigente,
    }
    cambios = [campo for campo, valor in datos.items() if getattr(membresia, campo) != valor]
    if membresia_id is not None and {"horas_organizador", "horas_invitado"}.intersection(cambios) and membresia.contrataciones.exists():
        raise ValidationError("Los cupos mensuales no se pueden cambiar en una membresía con contrataciones.")
    for campo, valor in datos.items():
        setattr(membresia, campo, valor)
    if membresia_id is not None and not cambios:
        return membresia
    with contexto_auditoria(usuario):
        _guardar_producto(membresia, campos=cambios + ["actualizado_en"] if membresia_id is not None else None)
    return membresia


@transaction.atomic
def cambiar_estado_membresia(usuario, membresia_id, estado, *, version):
    usuario = exigir_administracion_membresias(usuario, bloquear=True)
    membresia = Membresia.objects.select_for_update().get(pk=membresia_id)
    if estado not in Membresia.Estado.values:
        raise ValidationError("Elegí un estado válido para la membresía.")
    if membresia.estado == estado:
        return membresia
    _validar_version_producto(usuario, membresia, version)
    membresia.estado = estado
    with contexto_auditoria(usuario):
        _guardar_producto(membresia, campos=["estado", "actualizado_en"])
    return membresia
