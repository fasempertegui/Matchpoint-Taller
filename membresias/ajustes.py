from common.validaciones import validar_motivo

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios
from reservas.horas import resumen_horas_del_mes, saldo_horas_contratacion

from .models import AjusteHorasMembresia, MembresiaUsuario
from .servicios import exigir_administracion_membresias


def admite_ajustes(contratacion):
    return contratacion.estado == MembresiaUsuario.Estado.ACTIVO and contratacion.mes_cubierto >= timezone.localdate().replace(day=1)


def contexto_horas_contratacion(contratacion, parametros, *, administrador=False):
    historial = contratacion.ajustes_horas.select_related("registrado_por", "reversion_de", "reversion")
    return {
        "resumen_horas": resumen_horas_del_mes(contratacion.usuario_id, contratacion.mes_cubierto, contratacion),
        "ajustes_horas": Paginator(historial, 25).get_page(parametros.get("pagina_ajustes")),
        "puede_ajustar_horas": administrador and admite_ajustes(contratacion),
    }


def _preparar_ajuste(actor, contratacion_id, *, tipo_horas, operacion, cantidad, motivo, reversion_de_id=None):
    exigir_administracion_membresias(actor)
    try:
        titular_id = MembresiaUsuario.objects.values_list("usuario_id", flat=True).get(pk=contratacion_id)
    except MembresiaUsuario.DoesNotExist:
        raise ValidationError("La contratación no existe.") from None
    usuarios = bloquear_usuarios({actor.pk, titular_id})
    actor = exigir_administracion_membresias(usuarios.get(actor.pk))
    contratacion = MembresiaUsuario.objects.select_for_update(of=("self",)).select_related("usuario", "membresia").get(pk=contratacion_id)
    if not admite_ajustes(contratacion):
        raise ValidationError("Sólo se ajustan contrataciones Activas del mes vigente o de un período futuro.")
    motivo = motivo.strip() if isinstance(motivo, str) else ""
    validar_motivo(motivo)
    original = None
    if reversion_de_id is not None:
        original = AjusteHorasMembresia.objects.filter(pk=reversion_de_id, membresia_usuario=contratacion).first()
        if original is None or original.reversion_de_id is not None:
            raise ValidationError("Elegí un ajuste original de esta contratación para revertir.")
        if AjusteHorasMembresia.objects.filter(reversion_de=original).exists():
            raise ValidationError("El ajuste ya fue revertido.")
        tipo_horas, cantidad = original.tipo_horas, original.cantidad
        operacion = "quitar" if original.operacion == "otorgar" else "otorgar"
    if tipo_horas not in AjusteHorasMembresia.TipoHoras.values or operacion not in AjusteHorasMembresia.Operacion.values:
        raise ValidationError("Elegí un tipo de horas y una operación válidos.")
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= 32767:
        raise ValidationError("La cantidad debe ser un número entero positivo de hasta 32767 horas.")
    saldo = saldo_horas_contratacion(contratacion, tipo_horas)
    efecto = cantidad if operacion == "otorgar" else -cantidad
    if operacion == "quitar" and cantidad > saldo["disponibles"]:
        raise ValidationError(f"Sólo podés descontar hasta {saldo['disponibles']} horas disponibles.")
    if original is not None and saldo["saldo"] + efecto < 0:
        raise ValidationError("La reversión dejaría horas disponibles negativas.")
    datos = {
        "contratacion_id": contratacion.pk, "tipo_horas": tipo_horas, "operacion": operacion,
        "cantidad": cantidad, "motivo": motivo, "reversion_de_id": original.pk if original else None,
    }
    verificacion = {"actor": actor.pk, "datos": datos, "saldo": saldo, "estado": contratacion.estado}
    return {
        "actor": actor, "contratacion": contratacion, "original": original, "datos": datos,
        "saldo_actual": saldo["disponibles"], "saldo_resultante": max(0, saldo["saldo"] + efecto),
        "tipo_horas_texto": AjusteHorasMembresia.TipoHoras(tipo_horas).label,
        "operacion_texto": AjusteHorasMembresia.Operacion(operacion).label, "verificacion": verificacion,
    }


@transaction.atomic
def preparar_ajuste(actor, contratacion_id, *, tipo_horas="", operacion="", cantidad=None, motivo, reversion_de_id=None):
    revision = _preparar_ajuste(actor, contratacion_id, tipo_horas=tipo_horas, operacion=operacion,
                                cantidad=cantidad, motivo=motivo, reversion_de_id=reversion_de_id)
    revision["confirmacion"] = signing.dumps(revision["verificacion"], salt="membresias.ajustes_horas", compress=True)
    return revision


def leer_revision_ajuste(actor, confirmacion, *, contratacion_id, reversion_de_id=None):
    exigir_administracion_membresias(actor)
    try:
        firmado = signing.loads(confirmacion, salt="membresias.ajustes_horas", max_age=900)
        if firmado["actor"] != actor.pk or firmado["datos"]["contratacion_id"] != contratacion_id or firmado["datos"]["reversion_de_id"] != reversion_de_id:
            raise signing.BadSignature
    except (signing.BadSignature, KeyError, TypeError):
        raise ValidationError("La revisión venció o no es válida. Revisá nuevamente el ajuste.") from None
    return firmado


@transaction.atomic
def confirmar_ajuste(actor, confirmacion, *, contratacion_id, reversion_de_id=None):
    firmado = leer_revision_ajuste(actor, confirmacion, contratacion_id=contratacion_id, reversion_de_id=reversion_de_id)
    datos = firmado["datos"].copy()
    datos.pop("contratacion_id")
    revision = _preparar_ajuste(actor, contratacion_id, **datos)
    if revision["verificacion"] != firmado:
        raise ValidationError("Las horas disponibles cambiaron. Revisá nuevamente el efecto del ajuste.")
    ajuste = AjusteHorasMembresia(
        membresia_usuario=revision["contratacion"], tipo_horas=datos["tipo_horas"], operacion=datos["operacion"],
        cantidad=datos["cantidad"], motivo=datos["motivo"], registrado_por=revision["actor"], reversion_de=revision["original"],
    )
    with contexto_auditoria(revision["actor"]):
        ajuste.full_clean()
        if not admite_ajustes(revision["contratacion"]):
            raise ValidationError("El período ya no admite ajustes. Revisá nuevamente la contratación.")
        ajuste.save()
    return ajuste
