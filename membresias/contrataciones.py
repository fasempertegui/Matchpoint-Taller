from common.validaciones import validar_motivo

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios
from usuarios.models import Rol, Usuario, UsuarioRol

from .fechas import validar_fecha_alta, validar_mes_contratacion
from .models import Membresia, MembresiaUsuario, Plan, PlanUsuario
from .servicios import exigir_administracion_membresias
from comunicaciones.contrataciones import avisar_contratacion, avisar_anulacion_contratacion


def _bloquear_titular(actor, usuario_id, *, exigir_activo=True):
    exigir_administracion_membresias(actor)
    usuarios = bloquear_usuarios({actor.pk, usuario_id})
    actor = exigir_administracion_membresias(actor)
    titular = usuarios.get(usuario_id)
    if titular is None or (exigir_activo and not titular.esta_habilitado):
        raise ValidationError("Elegí un usuario activo con correo verificado para registrar la contratación.")
    return actor, titular


class ContratacionExistente(ValidationError):
    def __init__(self, contratacion):
        self.contratacion = contratacion
        super().__init__("Ya existe una contratación de este tipo para el titular y mes elegidos. Podés consultarla.")


def _datos_revision(actor, titular, producto):
    datos = {
        "actor": actor.pk, "titular": titular.pk, "producto": producto.pk,
        "precio": str(producto.precio_vigente), "actualizado_en": producto.actualizado_en.isoformat(),
    }
    if isinstance(producto, Membresia):
        datos.update({"horas_organizador": producto.horas_organizador, "horas_invitado": producto.horas_invitado})
    return datos


def revision_precio_contratacion(actor, titular, producto):
    return signing.dumps(
        _datos_revision(actor, titular, producto),
        salt=f"membresias.precio_{producto._meta.model_name}",
    )


def _validar_revision_precio(actor, titular, producto, revision):
    try:
        datos = signing.loads(revision, salt=f"membresias.precio_{producto._meta.model_name}")
    except (signing.BadSignature, TypeError):
        raise ValidationError("La revisión del precio no es válida. Revisá el importe y volvé a confirmar.") from None
    if datos != _datos_revision(actor, titular, producto):
        raise ValidationError("La selección o sus condiciones cambiaron. Revisá los datos y volvé a confirmar.")


def _registrar_contratacion(
    actor, titular, *, modelo, producto_id, mes_cubierto, fecha_alta, revision_precio,
    observaciones="",
):
    es_plan = modelo is PlanUsuario
    modelo_producto = Plan if es_plan else Membresia
    campo_producto = "plan" if es_plan else "membresia"
    if es_plan and titular.tiene_rol(Rol.PROFESOR):
        raise ValidationError("Un usuario con rol Profesor no puede contratar planes de clases.")
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
    _validar_revision_precio(actor, titular, producto, revision_precio)
    contratacion = modelo(
        usuario=titular, **{campo_producto: producto}, mes_cubierto=mes_cubierto, fecha_alta=fecha_alta,
        precio_aplicado=producto.precio_vigente, registrado_por=actor, observaciones=observaciones.strip(),
        estado=modelo.Estado.VENCIDO if mes_cubierto < timezone.localdate().replace(day=1)
        else modelo.Estado.ACTIVO,
    )
    if not es_plan:
        contratacion.horas_organizador_aplicadas = producto.horas_organizador
        contratacion.horas_invitado_aplicadas = producto.horas_invitado
    contratacion.full_clean()
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            contratacion.save()
            if es_plan and contratacion.estado == modelo.Estado.ACTIVO and not titular.tiene_rol(Rol.ADMINISTRADOR):
                UsuarioRol.objects.get_or_create(
                    usuario=titular, rol=Rol.objects.get(codigo=Rol.ALUMNO), defaults={"asignado_por": actor},
                )
            avisar_contratacion(contratacion, "plan" if es_plan else "membresia")
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
    if modelo is MembresiaUsuario:
        from django.db.models import Q
        from reservas.models import Reserva
        if Reserva.objects.filter(
            Q(membresia_usuario=contratacion) | Q(invitados__membresia_usuario=contratacion, invitados__condicion_aplicada="socio",
                invitados__respuesta__in=("pendiente", "afirmativa")),
            evento__estado="programado",
        ).exists():
            raise ValidationError("La membresía está aplicada en una reserva Programada como organizador o invitado socio.")
    motivo = motivo.strip()
    validar_motivo(motivo)
    contratacion.estado = modelo.Estado.ANULADO
    contratacion.motivo_anulacion = motivo
    contratacion.anulado_por = actor
    contratacion.anulado_en = timezone.now()
    contratacion.full_clean()
    with contexto_auditoria(actor):
        contratacion.save(update_fields=[
            "estado", "motivo_anulacion", "anulado_por", "anulado_en", "actualizado_en",
        ])
        avisar_anulacion_contratacion(contratacion, tipo)
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
