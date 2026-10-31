from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario, UsuarioRol

from .fechas import validar_fecha_alta, validar_mes_contratacion
from .models import Pase, PaseUsuario, Plan, PlanUsuario
from .servicios import exigir_administracion_membresias


def _bloquear_titular(actor, usuario_id):
    exigir_administracion_membresias(actor)
    usuarios = {
        usuario.pk: usuario for usuario in Usuario.objects.select_for_update()
        .filter(pk__in=(actor.pk, usuario_id)).order_by("pk")
    }
    actor = exigir_administracion_membresias(actor)
    titular = usuarios.get(usuario_id)
    if titular is None or not titular.is_active:
        raise ValidationError("Elegí un usuario activo para registrar la contratación.")
    return actor, titular


@transaction.atomic
def registrar_contratacion_plan(
    actor, *, usuario_id, plan_id, mes_cubierto, fecha_alta, precio_aplicado, observaciones="",
):
    actor, titular = _bloquear_titular(actor, usuario_id)
    if titular.tiene_rol(Rol.PROFESOR):
        raise ValidationError("Un usuario con rol Profesor no puede contratar planes de clases.")
    try:
        plan = Plan.objects.select_for_update().get(pk=plan_id)
    except Plan.DoesNotExist:
        raise ValidationError("El plan seleccionado ya no está disponible.") from None
    if plan.estado != Plan.Estado.ACTIVO:
        raise ValidationError("Elegí un plan activo para registrar la contratación.")
    validar_mes_contratacion(mes_cubierto)
    validar_fecha_alta(fecha_alta)
    if PlanUsuario.objects.filter(usuario=titular, mes_cubierto=mes_cubierto).exclude(
        estado=PlanUsuario.Estado.ANULADO,
    ).exists():
        raise ValidationError("El usuario ya tiene una contratación de plan para ese mes.")
    contratacion = PlanUsuario(
        usuario=titular, plan=plan, mes_cubierto=mes_cubierto, fecha_alta=fecha_alta,
        precio_aplicado=precio_aplicado, registrado_por=actor, observaciones=observaciones.strip(),
        estado=PlanUsuario.Estado.VENCIDO if mes_cubierto < timezone.localdate().replace(day=1)
        else PlanUsuario.Estado.ACTIVO,
    )
    contratacion.full_clean()
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            contratacion.save()
            if contratacion.estado == PlanUsuario.Estado.ACTIVO and not titular.tiene_rol(Rol.ADMINISTRADOR):
                UsuarioRol.objects.get_or_create(
                    usuario=titular, rol=Rol.objects.get(codigo=Rol.ALUMNO), defaults={"asignado_por": actor},
                )
    except IntegrityError as error:
        restriccion = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if restriccion == "plan_usuario_mes_no_anulado_unico":
            raise ValidationError("El usuario ya tiene una contratación de plan para ese mes.") from None
        raise
    return contratacion


@transaction.atomic
def registrar_contratacion_pase(
    actor, *, usuario_id, pase_id, mes_cubierto, fecha_alta, precio_aplicado, observaciones="",
):
    actor, titular = _bloquear_titular(actor, usuario_id)
    try:
        pase = Pase.objects.select_for_update().get(pk=pase_id)
    except Pase.DoesNotExist:
        raise ValidationError("El pase seleccionado ya no está disponible.") from None
    if pase.estado != Pase.Estado.ACTIVO:
        raise ValidationError("Elegí un pase activo para registrar la contratación.")
    if precio_aplicado != pase.precio_vigente:
        raise ValidationError("El precio vigente del pase cambió. Volvé a elegir el pase para revisar el importe.")
    validar_mes_contratacion(mes_cubierto)
    validar_fecha_alta(fecha_alta)
    if PaseUsuario.objects.filter(usuario=titular, mes_cubierto=mes_cubierto).exclude(
        estado=PaseUsuario.Estado.ANULADO,
    ).exists():
        raise ValidationError("El usuario ya tiene una contratación de pase para ese mes.")
    contratacion = PaseUsuario(
        usuario=titular, pase=pase, mes_cubierto=mes_cubierto, fecha_alta=fecha_alta,
        precio_aplicado=pase.precio_vigente, registrado_por=actor, observaciones=observaciones.strip(),
        estado=PaseUsuario.Estado.VENCIDO if mes_cubierto < timezone.localdate().replace(day=1)
        else PaseUsuario.Estado.ACTIVO,
    )
    contratacion.full_clean()
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            contratacion.save()
    except IntegrityError as error:
        restriccion = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
        if restriccion == "pase_usuario_mes_no_anulado_unico":
            raise ValidationError("El usuario ya tiene una contratación de pase para ese mes.") from None
        raise
    return contratacion
