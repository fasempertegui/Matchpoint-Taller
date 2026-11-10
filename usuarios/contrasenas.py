from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from auditoria.contexto import contexto_auditoria
from auditoria.models import LogAuditoria
from comunicaciones.servicios import encolar_email

from .models import Usuario
from .tokens import TokenRecuperacion, huella_recuperacion


RESPUESTA_RECUPERACION = "Si la cuenta está habilitada y su correo está verificado, recibirás un enlace para recuperar tu contraseña."


@transaction.atomic
def solicitar_recuperacion(email):
    usuario = Usuario.objects.select_for_update().filter(email__iexact=email, is_active=True, correo_verificado_en__isnull=False).first()
    if usuario is not None and usuario.has_usable_password():
        encolar_email(
            clave=f"recuperacion:{usuario.pk}:{uuid4()}", tipo="recuperacion", destinatario=usuario.email,
            datos={
                "mensaje": {"parrafos": ["Solicitaste recuperar tu contraseña. El enlace vence a los quince minutos de su emisión. Si no lo solicitaste, podés ignorar este mensaje."], "acciones": [{"texto": "Elegir una contraseña", "enlace_acceso": True}]},
                "vigencia": {"usuario_id": usuario.pk},
                "enlace": {"ruta": "/cuentas/recuperar/", "proposito": "recuperacion", "datos": {"usuario_id": usuario.pk, "solicitud": huella_recuperacion(usuario)}},
            },
        )
    return RESPUESTA_RECUPERACION


@sensitive_variables("nueva_contrasena", "contrasena_actual")
@transaction.atomic
def guardar_contrasena_propia(usuario_id, nueva_contrasena, *, contrasena_actual=None, token=None):
    usuario = Usuario.objects.select_for_update().get(pk=usuario_id)
    if not usuario.is_active:
        raise ValidationError("La cuenta no está habilitada.")
    if token is not None:
        if not TokenRecuperacion().check_token(usuario, token):
            raise ValidationError("El enlace venció o ya no es válido. Solicitá otro.")
    else:
        with contexto_auditoria(usuario, accion=LogAuditoria.Accion.ACTUALIZACION_HASH):
            if contrasena_actual is None or not usuario.check_password(contrasena_actual):
                raise ValidationError("La contraseña actual no es correcta.")
    if check_password(nueva_contrasena, usuario.password):
        raise ValidationError("La nueva contraseña debe ser diferente de la actual.")
    validate_password(nueva_contrasena, usuario)
    with contexto_auditoria(usuario, accion=LogAuditoria.Accion.CAMBIO_CONTRASENA):
        usuario.set_password(nueva_contrasena)
        usuario.debe_cambiar_contrasena = False
        usuario.save(update_fields=["password", "debe_cambiar_contrasena", "actualizado_en"])
        encolar_email(
            clave=f"contrasena:{usuario.pk}:{uuid4()}", tipo="contrasena_cambiada", destinatario=usuario.email,
            datos={"vigencia": {"usuario_id": usuario.pk}, "mensaje": {
                "parrafos": ["Cambiaste tu contraseña. Si no realizaste este cambio, recuperá el acceso a tu cuenta."],
                "acciones": [{"texto": "Recuperar mi contraseña", "ruta": "/cuentas/recuperar/"}],
            }},
        )
    return usuario
