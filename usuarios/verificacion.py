from datetime import datetime, timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from comunicaciones.servicios import encolar_email

from .models import Rol, Usuario, UsuarioRol


RESPUESTA_REENVIO = "Si la cuenta necesita verificar su correo, recibirás un enlace cuando corresponda."


def _encolar_verificacion(usuario, tipo, clave):
    parrafos = ["Verificá tu correo para habilitar las operaciones de tu cuenta. El enlace vence a los 15 minutos de su emisión."]
    if usuario.debe_cambiar_contrasena:
        parrafos.append("También deberás reemplazar tu contraseña provisoria. Si no la conocés, después de verificar podrás recuperar tu contraseña.")
    return encolar_email(
        clave=clave, tipo=tipo, destinatario=usuario.email,
        datos={
            "mensaje": {"parrafos": parrafos, "acciones": [{"texto": "Verificar mi correo", "enlace_acceso": True}]},
            "vigencia": {"usuario_id": usuario.pk, "solicitud": {"campo": "revision_correo", "valor": usuario.revision_correo}},
            "enlace": {"ruta": "/cuentas/verificar/", "proposito": "verificacion", "datos": {"usuario_id": usuario.pk, "correo": usuario.email, "solicitud": str(usuario.revision_correo)}},
        },
    )


def preparar_bienvenida(usuario):
    return _encolar_verificacion(usuario, "bienvenida", f"bienvenida:{usuario.pk}")


@transaction.atomic
def reenviar_verificacion(email):
    usuario = Usuario.objects.select_for_update().filter(email__iexact=email).first()
    ahora = timezone.now()
    if usuario is not None and usuario.correo_verificado_en is None and (
        usuario.verificacion_solicitada_en is None or ahora >= usuario.verificacion_solicitada_en + timedelta(minutes=5)
    ):
        usuario.verificacion_solicitada_en = ahora
        usuario.save(update_fields=["verificacion_solicitada_en"])
        _encolar_verificacion(usuario, "verificacion", f"verificacion:{usuario.pk}:{ahora.isoformat()}")
    return RESPUESTA_REENVIO


@transaction.atomic
def corregir_correo_inicial(actor, email, contrasena):
    usuario = Usuario.objects.select_for_update().get(pk=actor.pk)
    if usuario.correo_verificado_en is not None:
        raise ValidationError("El correo ya está verificado.")
    if not usuario.is_active or not usuario.check_password(contrasena):
        raise ValidationError("No se pudo corregir el correo. Revisá los datos ingresados.")
    return _guardar_correccion(usuario, email, usuario)


def _guardar_correccion(usuario, email, responsable):
    email = email.strip()
    validate_email(email)
    if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
        raise ValidationError("Ese correo no está disponible.")
    if usuario.email.casefold() == email.casefold():
        raise ValidationError("Ingresá el correo corregido o solicitá un reenvío.")
    try:
        with transaction.atomic(), contexto_auditoria(responsable):
            usuario.email = email
            usuario.revision_correo += 1
            usuario.verificacion_solicitada_en = timezone.now()
            usuario.save(update_fields=["email", "revision_correo", "verificacion_solicitada_en", "actualizado_en"])
            _encolar_verificacion(usuario, "verificacion", f"correccion:{usuario.pk}:{usuario.revision_correo}")
    except IntegrityError:
        raise ValidationError("Ese correo no está disponible.") from None
    return usuario


@transaction.atomic
def corregir_correo_inicial_por_administracion(actor, usuario_id, email, *, contrasena):
    from django.core.exceptions import PermissionDenied
    from common.bloqueos import bloquear_usuarios
    from .acceso import exigir_acceso_operativo

    actor = exigir_acceso_operativo(actor)
    usuarios = bloquear_usuarios({actor.pk, usuario_id})
    actor = exigir_acceso_operativo(usuarios.get(actor.pk))
    if not actor.has_perm("usuarios.change_usuario"):
        raise PermissionDenied
    if not actor.check_password(contrasena):
        raise ValidationError({"contrasena": "La contraseña no es correcta."})
    usuario = usuarios.get(usuario_id)
    if usuario is None or usuario.correo_verificado_en is not None:
        raise ValidationError("La corrección inicial requiere una cuenta sin verificar.")
    return _guardar_correccion(usuario, email, actor)


def leer_enlace_verificacion(token):
    return leer_enlace_cuenta(token, "verificacion")


def leer_enlace_cuenta(token, proposito):
    try:
        datos = signing.Signer(salt=f"comunicaciones.{proposito}").unsign_object(token)
        if type(datos["usuario_id"]) is not int or not isinstance(datos["correo"], str):
            raise ValueError
        emision = datetime.fromisoformat(datos["emitido_en"])
        if timezone.is_naive(emision):
            raise ValueError
        return datos, emision
    except (signing.BadSignature, ValueError, TypeError, KeyError, UnicodeError):
        raise ValidationError("El enlace no es válido. Solicitá uno nuevo.") from None


def _comprobar_enlace(usuario, datos, emision):
    if usuario is None:
        return "La cuenta ya no está disponible. Podés iniciar un nuevo registro."
    if usuario.email.casefold() != datos["correo"].casefold() or datos.get("solicitud") != str(usuario.revision_correo):
        raise ValidationError("El enlace corresponde a otro correo. Solicitá uno nuevo.")
    if usuario.correo_verificado_en is not None:
        return "El correo ya está verificado."
    ahora = timezone.now()
    if emision > ahora or ahora >= emision + timedelta(minutes=15):
        raise ValidationError("El enlace venció. Solicitá uno nuevo.")
    return ""


def consultar_verificacion(token):
    datos, emision = leer_enlace_verificacion(token)
    usuario = Usuario.objects.filter(pk=datos["usuario_id"]).first()
    return _comprobar_enlace(usuario, datos, emision)


@transaction.atomic
def verificar_correo(token):
    datos, emision = leer_enlace_verificacion(token)
    usuario = Usuario.objects.select_for_update().filter(pk=datos["usuario_id"]).first()
    resultado = _comprobar_enlace(usuario, datos, emision)
    if resultado:
        return resultado
    with contexto_auditoria(usuario):
        usuario.correo_verificado_en = timezone.now()
        usuario.save(update_fields=["correo_verificado_en", "actualizado_en"])
        if not usuario.is_superuser and not usuario.tiene_rol(Rol.ADMINISTRADOR):
            # Verificar asigna Reservas también a una cuenta inactiva, sin habilitarla.
            UsuarioRol.objects.bulk_create(
                [UsuarioRol(usuario=usuario, rol=Rol.objects.get(codigo=Rol.RESERVAS))], ignore_conflicts=True,
            )
    return "Tu correo está verificado."
