from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios
from comunicaciones.servicios import encolar_email
from comunicaciones.models import EnvioEmail

from .acceso import exigir_acceso_operativo
from .models import Usuario
from .verificacion import _guardar_correccion, leer_enlace_cuenta


def _aviso_correo(usuario, direccion, tipo, clave, texto, *, revision=None, confirmar=False):
    datos = {"vigencia": {"usuario_id": usuario.pk}, "mensaje": {"parrafos": [texto]}}
    if revision is not None:
        datos["vigencia"]["solicitud"] = {"campo": "revision_correo", "valor": revision}
    if confirmar:
        datos["enlace"] = {"ruta": "/cuentas/confirmar-correo/", "proposito": "cambio_correo", "datos": {"usuario_id": usuario.pk, "correo": direccion, "solicitud": str(revision)}}
        datos["mensaje"]["acciones"] = [{"texto": "Confirmar mi correo", "enlace_acceso": True}]
    return encolar_email(clave=clave, tipo=tipo, destinatario=direccion, datos=datos)


@transaction.atomic
def solicitar_cambio_correo(actor, usuario_id, email, *, contrasena):
    actor = exigir_acceso_operativo(actor)
    usuarios = bloquear_usuarios({actor.pk, usuario_id})
    actor = exigir_acceso_operativo(usuarios.get(actor.pk))
    if not actor.has_perm("usuarios.change_usuario"):
        raise PermissionDenied
    if not actor.check_password(contrasena):
        raise ValidationError({"contrasena": "La contraseña no es correcta."})
    usuario = usuarios.get(usuario_id)
    if usuario is None:
        raise ValidationError("La cuenta ya no está disponible.")
    if usuario.correo_verificado_en is None:
        return _guardar_correccion(usuario, email, actor)
    email = email.strip()
    validate_email(email)
    if usuario.email.casefold() == email.casefold():
        raise ValidationError("Ingresá un correo diferente del vigente.")
    if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
        raise ValidationError("Ese correo no está disponible.")
    if usuario.email_pendiente.casefold() == email.casefold():
        actual = EnvioEmail.objects.filter(clave=f"confirmar_correo:{usuario.pk}:{usuario.revision_correo}").first()
        if actual is not None and actual.estado not in (EnvioEmail.Estado.FALLIDO, EnvioEmail.Estado.DESCARTADO) and (
            actual.enlace_emitido_en is None or timezone.now() < actual.enlace_emitido_en + timedelta(minutes=15)
        ):
            return usuario
    with contexto_auditoria(actor):
        usuario.email_pendiente = email
        usuario.cambio_email_solicitado_en = timezone.now()
        usuario.revision_correo += 1
        usuario.save(update_fields=["email_pendiente", "cambio_email_solicitado_en", "revision_correo", "actualizado_en"])
        revision = usuario.revision_correo
        _aviso_correo(usuario, usuario.email, "solicitud_correo", f"solicitud_correo:{usuario.pk}:{revision}", "Se solicitó cambiar el correo de tu cuenta. Tu dirección vigente se conserva hasta confirmar la solicitud.", revision=revision)
        _aviso_correo(usuario, email, "confirmar_correo", f"confirmar_correo:{usuario.pk}:{revision}", "Confirmá esta dirección para completar el cambio de correo de tu cuenta. El enlace vence a los quince minutos de su emisión.", revision=revision, confirmar=True)
    return usuario


def _comprobar_cambio(usuario, datos, emision):
    if usuario is None or usuario.correo_verificado_en is None:
        raise ValidationError("La cuenta no está disponible para este cambio.")
    if not usuario.email_pendiente or usuario.cambio_email_solicitado_en is None or datos.get("solicitud") != str(usuario.revision_correo) or datos["correo"] != usuario.email_pendiente:
        raise ValidationError("La solicitud ya no está vigente.")
    ahora = timezone.now()
    if emision > ahora or ahora >= emision + timedelta(minutes=15):
        raise ValidationError("El enlace venció. Solicitá otro cambio a administración.")


def consultar_cambio_correo(token):
    datos, emision = leer_enlace_cuenta(token, "cambio_correo")
    usuario = Usuario.objects.filter(pk=datos["usuario_id"]).first()
    _comprobar_cambio(usuario, datos, emision)


@transaction.atomic
def confirmar_cambio_correo(token):
    datos, emision = leer_enlace_cuenta(token, "cambio_correo")
    usuario = Usuario.objects.select_for_update().filter(pk=datos["usuario_id"]).first()
    _comprobar_cambio(usuario, datos, emision)
    nuevo = usuario.email_pendiente
    if Usuario.objects.filter(email__iexact=nuevo).exclude(pk=usuario.pk).exists():
        raise ValidationError("Ese correo ya no está disponible. El cambio no se aplicó.")
    anterior, revision = usuario.email, usuario.revision_correo
    try:
        with transaction.atomic(), contexto_auditoria(usuario):
            usuario.email = nuevo
            usuario.email_pendiente = ""
            usuario.cambio_email_solicitado_en = None
            usuario.revision_correo += 1
            usuario.save(update_fields=["email", "email_pendiente", "cambio_email_solicitado_en", "revision_correo", "actualizado_en"])
            for destino, direccion in (("anterior", anterior), ("nuevo", nuevo)):
                _aviso_correo(usuario, direccion, "correo_cambiado", f"correo_cambiado:{usuario.pk}:{revision}:{destino}", "Se completó el cambio de correo de tu cuenta.")
    except IntegrityError as error:
        if getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) != "usuario_email_unico_sin_mayusculas":
            raise
        raise ValidationError("Ese correo ya no está disponible. El cambio no se aplicó.") from None
    return usuario
