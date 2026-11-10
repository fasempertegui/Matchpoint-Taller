from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format, number_format

from .models import EnvioEmail


class DescartarEnvio(Exception):
    pass


def _validar_ruta(ruta):
    if not isinstance(ruta, str) or not ruta.startswith("/") or ruta.startswith("//") or "\\" in ruta or any(ord(c) < 32 for c in ruta):
        raise ValidationError("El enlace debe pertenecer al sitio de la academia.")


def url_publica(ruta):
    _validar_ruta(ruta)
    base = settings.EMAILS_URL_PUBLICA.rstrip("/")
    try:
        URLValidator(schemes=["http", "https"])(base)
        partes = urlsplit(base)
        if partes.username or partes.password or partes.query or partes.fragment or partes.path:
            raise ValueError
    except (ValidationError, ValueError):
        raise ImproperlyConfigured("Configurá un origen público válido para los emails.") from None
    return base + ruta


def dato_fecha(etiqueta, fecha):
    return {"etiqueta": etiqueta, "valor": date_format(fecha, "d/m/Y")}


def dato_hora(etiqueta, hora):
    return {"etiqueta": etiqueta, "valor": hora.strftime("%H:%M")}


def dato_importe(etiqueta, importe):
    return {"etiqueta": etiqueta, "valor": "ARS " + number_format(Decimal(importe), decimal_pos=2, use_l10n=True, force_grouping=True)}


def _validar_bloque(bloque, *, principal=False):
    permitidos = {"parrafos", "datos", "acciones", "apartados"} if principal else {"titulo", "parrafos", "datos", "acciones"}
    if not isinstance(bloque, dict) or set(bloque) - permitidos:
        raise ValidationError("El contenido del email no es válido.")
    if not isinstance(bloque.get("titulo", ""), str):
        raise ValidationError("El título del apartado no es válido.")
    for campo in ("parrafos", "datos", "acciones", "apartados"):
        if not isinstance(bloque.get(campo, []), list):
            raise ValidationError("El contenido del email no es válido.")
    if not all(isinstance(parrafo, str) for parrafo in bloque.get("parrafos", [])):
        raise ValidationError("El texto del email no es válido.")
    for dato in bloque.get("datos", []):
        if not isinstance(dato, dict) or set(dato) != {"etiqueta", "valor"} or not all(isinstance(v, str) for v in dato.values()):
            raise ValidationError("Los datos visibles del email no son válidos.")
    for accion in bloque.get("acciones", []):
        if not isinstance(accion, dict) or set(accion) - {"texto", "ruta", "enlace_acceso"} or not isinstance(accion.get("texto"), str):
            raise ValidationError("La acción del email no es válida.")
        if "enlace_acceso" in accion and accion["enlace_acceso"] is not True:
            raise ValidationError("El enlace de acceso no es válido.")
        if not accion.get("enlace_acceso"):
            _validar_ruta(accion.get("ruta"))
    for apartado in bloque.get("apartados", []):
        _validar_bloque(apartado)


def validar_datos(datos):
    if not isinstance(datos, dict) or "mensaje" not in datos or set(datos) - {"mensaje", "vigencia", "enlace"}:
        raise ValidationError("Los datos del email no son válidos.")
    mensaje = datos["mensaje"]
    _validar_bloque(mensaje, principal=True)
    vigencia = datos.get("vigencia", {})
    if not isinstance(vigencia, dict) or set(vigencia) - {"usuario_id", "evento_id", "vencer_en", "solicitud", "participacion", "contratacion"}:
        raise ValidationError("La vigencia del email no es válida.")
    for campo in ("usuario_id", "evento_id"):
        if campo in vigencia and (type(vigencia[campo]) is not int or vigencia[campo] <= 0):
            raise ValidationError("El identificador del aviso no es válido.")
    if "vencer_en" in vigencia:
        try:
            vencimiento = datetime.fromisoformat(vigencia["vencer_en"])
            if timezone.is_naive(vencimiento):
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError("El vencimiento debe incluir zona horaria.") from None
    solicitud = vigencia.get("solicitud")
    if solicitud is not None and (not isinstance(solicitud, dict) or set(solicitud) != {"campo", "valor"}):
        raise ValidationError("La solicitud del aviso no es válida.")
    contratacion = vigencia.get("contratacion")
    if contratacion is not None and (
        not isinstance(contratacion, dict) or set(contratacion) != {"tipo", "id"}
        or contratacion["tipo"] not in ("plan", "membresia") or type(contratacion["id"]) is not int or contratacion["id"] <= 0
    ):
        raise ValidationError("La contratación del aviso no es válida.")
    participacion = vigencia.get("participacion")
    if participacion is not None and (not isinstance(participacion, dict) or set(participacion) != {"tipo", "actividad_id", "identidad"}):
        raise ValidationError("La participación del aviso no es válida.")
    enlace = datos.get("enlace")
    if enlace is not None:
        if not isinstance(enlace, dict) or set(enlace) != {"ruta", "proposito", "datos"}:
            raise ValidationError("La preparación del enlace no es válida.")
        if enlace["proposito"] not in ("verificacion", "cambio_correo", "recuperacion"):
            raise ValidationError("El propósito del enlace no es válido.")
        _validar_ruta(enlace["ruta"])
        if urlsplit(enlace["ruta"]).query or urlsplit(enlace["ruta"]).fragment:
            raise ValidationError("La ruta de confirmación no admite parámetros.")
        if not isinstance(enlace["datos"], dict) or set(enlace["datos"]) - {"usuario_id", "correo", "solicitud"} or any(not isinstance(v, (str, int)) for v in enlace["datos"].values()):
            raise ValidationError("El enlace contiene datos no permitidos.")
    for bloque in [mensaje, *mensaje.get("apartados", [])]:
        for accion in bloque.get("acciones", []):
            if accion.get("enlace_acceso") and (enlace is None or "ruta" in accion):
                raise ValidationError("El enlace de acceso no es válido.")


def verificar_vigencia(envio):
    from usuarios.models import Usuario
    from reservas.models import Evento

    ahora = timezone.now()
    vigencia = envio.datos.get("vigencia", {})
    if vigencia.get("vencer_en") and ahora >= datetime.fromisoformat(vigencia["vencer_en"]):
        raise DescartarEnvio("El plazo del aviso terminó.")
    if envio.enlace_emitido_en and ahora >= envio.enlace_emitido_en + timedelta(minutes=15):
        raise DescartarEnvio("El enlace venció.")
    usuario = None
    if vigencia.get("usuario_id"):
        usuario = Usuario.objects.filter(pk=vigencia["usuario_id"]).first()
        if usuario is None:
            raise DescartarEnvio("La cuenta ya no está disponible.")
        if envio.tipo in (EnvioEmail.Tipo.BIENVENIDA, EnvioEmail.Tipo.VERIFICACION) and usuario.correo_verificado_en is not None:
            raise DescartarEnvio("El correo ya está verificado.")
        tipos_cuenta = {EnvioEmail.Tipo.BIENVENIDA, EnvioEmail.Tipo.VERIFICACION, EnvioEmail.Tipo.ESTADO_CUENTA, EnvioEmail.Tipo.CONTRASENA_CAMBIADA, EnvioEmail.Tipo.SOLICITUD_CORREO, EnvioEmail.Tipo.CONFIRMAR_CORREO, EnvioEmail.Tipo.CORREO_CAMBIADO}
        if usuario.correo_verificado_en is None and envio.tipo not in tipos_cuenta:
            raise DescartarEnvio("El correo no está verificado.")
        if envio.tipo == EnvioEmail.Tipo.RECUPERACION:
            from usuarios.tokens import huella_recuperacion

            if not usuario.has_usable_password() or envio.datos.get("enlace", {}).get("datos", {}).get("solicitud") != huella_recuperacion(usuario):
                raise DescartarEnvio("La solicitud de recuperación ya no está vigente.")
        excepciones = {EnvioEmail.Tipo.BIENVENIDA, EnvioEmail.Tipo.VERIFICACION, EnvioEmail.Tipo.ESTADO_CUENTA, EnvioEmail.Tipo.CORREO_CAMBIADO, EnvioEmail.Tipo.SOLICITUD_CORREO, EnvioEmail.Tipo.CONFIRMAR_CORREO}
        if not usuario.is_active and envio.tipo not in excepciones:
            raise DescartarEnvio("La cuenta está deshabilitada.")
        if envio.tipo not in excepciones and usuario.email.casefold() != envio.destinatario.casefold():
            raise DescartarEnvio("La dirección destinataria cambió.")
    solicitud = vigencia.get("solicitud")
    if solicitud:
        campos = {campo.name for campo in Usuario._meta.fields}
        if usuario is None or solicitud.get("campo") not in {"email", "email_pendiente", "cambio_email_solicitado_en", "verificacion_solicitada_en", "revision_correo"} & campos:
            raise DescartarEnvio("La solicitud ya no está disponible.")
        valor = getattr(usuario, solicitud["campo"])
        valor = valor.isoformat() if isinstance(valor, datetime) else valor
        if valor != solicitud.get("valor"):
            raise DescartarEnvio("La solicitud fue sustituida.")
    recordatorios = {EnvioEmail.Tipo.RECORDATORIO_CLASE, EnvioEmail.Tipo.RECORDATORIO_RESERVA}
    if envio.tipo in recordatorios:
        evento = Evento.objects.select_related("turno").filter(pk=vigencia.get("evento_id")).first()
        if evento is None or evento.estado != Evento.Estado.PROGRAMADO:
            raise DescartarEnvio("La actividad ya no está programada.")
        inicio = timezone.make_aware(datetime.combine(evento.turno.fecha, evento.turno.hora_inicio))
        if ahora >= inicio:
            raise DescartarEnvio("La actividad ya comenzó.")
    referencia_contrato = vigencia.get("contratacion")
    if referencia_contrato:
        from membresias.continuidad import MODELOS_CONTINUIDAD

        modelo = MODELOS_CONTINUIDAD[referencia_contrato["tipo"]]
        contrato = modelo.objects.filter(pk=referencia_contrato["id"], usuario_id=vigencia.get("usuario_id")).first()
        if contrato is None or contrato.estado == modelo.Estado.ANULADO:
            raise DescartarEnvio("La contratación ya no está disponible.")
    participacion = vigencia.get("participacion")
    if participacion:
        from clases.models import ClaseAlumno, ClaseProfesor
        from reservas.models import ReservaInvitado

        modelos = {"profesor": ClaseProfesor, "participante": ClaseAlumno, "invitado": ReservaInvitado}
        modelo = modelos.get(participacion.get("tipo"))
        if modelo is None or usuario is None:
            raise DescartarEnvio("La participación no está disponible.")
        campo_persona = "profesor_id" if modelo == ClaseProfesor else "usuario_id"
        campo_actividad = "reserva_id" if modelo == ReservaInvitado else "clase_id"
        relacion = modelo.objects.filter(**{campo_persona: usuario.pk, campo_actividad: participacion.get("actividad_id")}).first()
        retiradas = {EnvioEmail.Tipo.RETIRADA_CLASE, EnvioEmail.Tipo.RETIRADA_INVITACION}
        if envio.tipo not in retiradas:
            if relacion is None:
                raise DescartarEnvio("La persona ya no está asignada.")
            if participacion.get("identidad") != str(relacion.identidad):
                raise DescartarEnvio("La participación fue sustituida.")
            if modelo == ReservaInvitado and relacion.respuesta == "negativa":
                raise DescartarEnvio("La invitación fue rechazada.")
            if modelo == ClaseAlumno and envio.tipo == EnvioEmail.Tipo.RECORDATORIO_CLASE and relacion.respuesta == "no_asistira":
                raise DescartarEnvio("La persona avisó que no asistirá.")

    return usuario


def preparar_mensaje(envio):
    validar_datos(envio.datos)
    usuario = verificar_vigencia(envio)
    return renderizar_mensaje(envio, usuario=usuario)


def renderizar_mensaje(envio, *, usuario=None):
    validar_datos(envio.datos)
    enlace = envio.datos.get("enlace")
    url_acceso = ""
    if enlace:
        if enlace["proposito"] == "recuperacion":
            from django.urls import reverse
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode
            from usuarios.models import Usuario
            from usuarios.tokens import TokenRecuperacion

            usuario = usuario or Usuario.objects.get(pk=enlace["datos"]["usuario_id"])
            token = TokenRecuperacion(emitido_en=envio.enlace_emitido_en).make_token(usuario)
            url_acceso = url_publica(reverse("password_reset_confirm", kwargs={"uidb64": urlsafe_base64_encode(force_bytes(usuario.pk)), "token": token}))
        else:
            contenido = {**enlace["datos"], "envio": str(envio.pk), "emitido_en": envio.enlace_emitido_en.isoformat()}
            token = signing.Signer(salt=f"comunicaciones.{enlace['proposito']}").sign_object(contenido)
            url_acceso = url_publica(enlace["ruta"]) + "?" + urlencode({"token": token})


    def preparar_bloque(bloque):
        return {**bloque, "acciones": [
            {"texto": accion["texto"], "url": url_acceso if accion.get("enlace_acceso") else url_publica(accion["ruta"])}
            for accion in bloque.get("acciones", [])
        ]}

    contenido = envio.datos.get("mensaje", {})
    contexto = {
        "titulo": envio.get_tipo_display(), "contenido": preparar_bloque(contenido),
        "apartados": [preparar_bloque(bloque) for bloque in contenido.get("apartados", [])],
        "logo_url": url_publica("/static/img/logo.png"),
    }
    return (
        envio.get_tipo_display(),
        render_to_string("comunicaciones/email/mensaje.txt", contexto),
        render_to_string("comunicaciones/email/mensaje.html", contexto),
    )
