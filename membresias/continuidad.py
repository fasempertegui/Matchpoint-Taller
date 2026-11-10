from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.bloqueos import bloquear_usuarios
from usuarios.acceso import exigir_acceso_operativo
from usuarios.models import Rol

from .fechas import mes_siguiente
from .models import MembresiaUsuario, PlanUsuario, RespuestaContinuidad

MODELOS_CONTINUIDAD = {"plan": PlanUsuario, "membresia": MembresiaUsuario}
ZONA_SALTA = ZoneInfo("America/Argentina/Salta")


def ventana_continuidad(mes):
    apertura = datetime.combine(mes.replace(day=25), time.min, tzinfo=ZONA_SALTA)
    cierre = datetime.combine(mes_siguiente(mes).replace(day=6), time.min, tzinfo=ZONA_SALTA)
    return apertura, cierre


def encuesta_abierta(contratacion):
    apertura, cierre = ventana_continuidad(contratacion.mes_cubierto)
    return contratacion.estado != contratacion.Estado.ANULADO and apertura <= timezone.now() < cierre


def contexto_continuidad(contratacion, actor, *, tipo):
    apertura, cierre = ventana_continuidad(contratacion.mes_cubierto)
    puede_responder = (
        actor.pk == contratacion.usuario_id and actor.esta_habilitado
        and not actor.debe_cambiar_contrasena and not actor.tiene_rol(Rol.ADMINISTRADOR)
        and encuesta_abierta(contratacion)
    )
    return {"continuidad": {
        "mes_consultado": mes_siguiente(contratacion.mes_cubierto),
        "apertura": apertura, "ultimo_dia": (cierre - timedelta(days=1)).date(),
        "respuesta": contratacion.get_respuesta_continuidad_display() or "Sin responder",
        "respondida_en": contratacion.continuidad_respondida_en,
        "puede_responder": puede_responder,
        "url_responder": reverse(f"membresias:mi_{tipo}_continuidad", args=[contratacion.pk]) if puede_responder else None,
    }}


@transaction.atomic
def responder_continuidad(actor, contratacion_id, respuesta, *, tipo):
    actor = exigir_acceso_operativo(actor)
    if actor.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    modelo = MODELOS_CONTINUIDAD[tipo]
    titular_id = modelo.objects.values_list("usuario_id", flat=True).get(pk=contratacion_id)
    if actor.pk != titular_id:
        raise PermissionDenied
    usuarios = bloquear_usuarios({actor.pk})
    actor = exigir_acceso_operativo(usuarios.get(actor.pk))
    if actor.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    contratacion = modelo.objects.select_for_update().get(pk=contratacion_id)
    if contratacion.usuario_id != actor.pk:
        raise PermissionDenied
    if not encuesta_abierta(contratacion):
        raise ValidationError("La encuesta no está disponible para responder.")
    if respuesta not in RespuestaContinuidad.values:
        raise ValidationError("Elegí una de las respuestas disponibles.")
    if contratacion.respuesta_continuidad == respuesta:
        return contratacion
    with contexto_auditoria(actor):
        contratacion.respuesta_continuidad = respuesta
        contratacion.continuidad_respondida_en = timezone.now()
        contratacion.save(update_fields=["respuesta_continuidad", "continuidad_respondida_en", "actualizado_en"])
        if not encuesta_abierta(contratacion):
            raise ValidationError("El plazo para responder terminó. No se guardó el cambio.")
    return contratacion
