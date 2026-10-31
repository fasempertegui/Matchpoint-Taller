from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario, UsuarioRol

from .fechas import validar_fecha_alta, validar_mes_contratacion
from .models import Pase, PaseUsuario, Plan, PlanUsuario
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


def anular_contratacion_pase(actor, contratacion_id, *, motivo, version):
    return _anular_contratacion(
        actor, contratacion_id, modelo=PaseUsuario, tipo="pase", motivo=motivo, version=version,
    )


def validar_retiro_rol_alumno(usuario):
    if PlanUsuario.objects.filter(usuario=usuario, estado=PlanUsuario.Estado.ACTIVO).exists():
        raise ValidationError("No se puede quitar el rol Alumno mientras el usuario tenga contrataciones de planes Activas.")


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
