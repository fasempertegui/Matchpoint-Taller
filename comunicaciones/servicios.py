import logging
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import connection, models, transaction
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.utils import timezone

from .mensajes import DescartarEnvio, preparar_mensaje, validar_datos
from .models import EnvioEmail

logger = logging.getLogger(__name__)
REINTENTOS_MINUTOS = (5, 15, 60)
RESERVA_MINUTOS = 5


def entrega_habilitada():
    return settings.EMAILS_HABILITADOS and (
        settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend"
        or settings.EMAILS_ENTREGA_EXTERNA_HABILITADA
    )


def _despertar_trabajador(envio_id):
    if not entrega_habilitada():
        return
    from .tasks import entregar_email

    try:
        entregar_email.apply_async(args=[str(envio_id)], retry=False)
    except Exception:
        logger.warning("No se pudo despertar la cola de emails; el barrido recuperará el pendiente.")


def encolar_email(*, clave, tipo, destinatario, datos):
    if not connection.in_atomic_block:
        raise RuntimeError("El email debe guardarse en la transacción de su operación.")
    validar_datos(datos)
    ahora = timezone.now()
    candidato = EnvioEmail(clave=clave, tipo=tipo, destinatario=destinatario, datos=datos)
    candidato.full_clean(validate_unique=False, validate_constraints=False)
    envio, creado = EnvioEmail.objects.get_or_create(
        clave=clave, defaults={"tipo": tipo, "destinatario": destinatario, "datos": datos, "creado_en": ahora, "proximo_intento_en": ahora},
    )
    if (envio.tipo, envio.destinatario, envio.datos) != (tipo, destinatario, datos):
        raise ValidationError("La clave del aviso corresponde a otro contenido.")
    if creado:
        transaction.on_commit(lambda: _despertar_trabajador(envio.pk))
    return envio


def _registrar_fallo(envio, ahora, error):
    envio.estado = EnvioEmail.Estado.FALLIDO if envio.intentos >= 4 else EnvioEmail.Estado.PENDIENTE
    if envio.estado == EnvioEmail.Estado.PENDIENTE:
        envio.proximo_intento_en = ahora + timedelta(minutes=REINTENTOS_MINUTOS[envio.intentos - 1])
    envio.reserva_token = None
    envio.reservado_hasta = None
    envio.error_resumido = error
    envio.save(update_fields=("estado", "proximo_intento_en", "reserva_token", "reservado_hasta", "error_resumido"))


@transaction.atomic
def reclamar_envio(envio_id=None):
    ahora = timezone.now()
    consulta = EnvioEmail.objects.select_for_update(skip_locked=True).filter(
        models.Q(estado=EnvioEmail.Estado.PENDIENTE, proximo_intento_en__lte=ahora)
        | models.Q(estado=EnvioEmail.Estado.EN_PROCESO, reservado_hasta__lte=ahora),
    ).order_by("proximo_intento_en", "creado_en", "pk")
    if envio_id is not None:
        consulta = consulta.filter(pk=envio_id)
    envio = consulta.first()
    if envio is None:
        return None
    if envio.estado == EnvioEmail.Estado.EN_PROCESO:
        _registrar_fallo(envio, ahora, "Se interrumpió el procesamiento del email.")
        return envio
    envio.estado = EnvioEmail.Estado.EN_PROCESO
    envio.reserva_token = uuid4()
    envio.reservado_hasta = ahora + timedelta(minutes=RESERVA_MINUTOS)
    envio.intentos += 1
    envio.ultimo_intento_en = ahora
    if envio.datos.get("enlace") and envio.enlace_emitido_en is None:
        envio.enlace_emitido_en = ahora.replace(microsecond=0) if envio.datos["enlace"]["proposito"] == "recuperacion" else ahora
    envio.save(update_fields=("estado", "reserva_token", "reservado_hasta", "intentos", "ultimo_intento_en", "enlace_emitido_en"))
    return envio


@transaction.atomic
def _terminar_envio(envio, estado, error=""):
    actual = EnvioEmail.objects.select_for_update().filter(
        pk=envio.pk, estado=EnvioEmail.Estado.EN_PROCESO, reserva_token=envio.reserva_token,
    ).first()
    if actual is None:
        return
    ahora = timezone.now()
    if estado == EnvioEmail.Estado.FALLIDO:
        _registrar_fallo(actual, ahora, error)
        return
    actual.estado = estado
    actual.error_resumido = error
    actual.aceptado_en = ahora if estado == EnvioEmail.Estado.ENVIADO else None
    actual.reserva_token = None
    actual.reservado_hasta = None
    actual.save(update_fields=("estado", "error_resumido", "aceptado_en", "reserva_token", "reservado_hasta"))


def procesar_envios(*, envio_id=None, limite=100):
    if not entrega_habilitada():
        return 0
    if connection.in_atomic_block:
        raise RuntimeError("La entrega debe ejecutarse fuera de la transacción de negocio.")
    procesados = 0
    for _ in range(limite):
        envio = reclamar_envio(envio_id)
        if envio is None:
            break
        procesados += 1
        if envio.estado == EnvioEmail.Estado.EN_PROCESO:
            try:
                asunto, texto, html = preparar_mensaje(envio)
            except (ImproperlyConfigured, TemplateDoesNotExist, TemplateSyntaxError):
                _terminar_envio(envio, EnvioEmail.Estado.FALLIDO, "No se pudo preparar el email. Revisá la configuración.")
            except DescartarEnvio as error:
                _terminar_envio(envio, EnvioEmail.Estado.DESCARTADO, str(error))
            except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
                _terminar_envio(envio, EnvioEmail.Estado.DESCARTADO, "Los datos del email no son válidos.")
            else:
                try:
                    mensaje = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [envio.destinatario])
                    mensaje.attach_alternative(html, "text/html")
                    if mensaje.send() != 1:
                        raise OSError
                except Exception:
                    # El proveedor puede incluir enlaces o credenciales en el texto de su error.
                    _terminar_envio(envio, EnvioEmail.Estado.FALLIDO, "El servicio de correo no confirmó la entrega.")
                else:
                    _terminar_envio(envio, EnvioEmail.Estado.ENVIADO)
        if envio_id is not None:
            break
    return procesados
