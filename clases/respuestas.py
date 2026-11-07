from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from common.disponibilidad import validar_disponibilidad
from common.respuestas import aplicar_respuesta
from reservas.models import Evento

from .models import ClaseAlumno
from .permisos import exigir_acceso_clases
from .servicios import _bloquear_clase, bloquear_usuarios_clase


@transaction.atomic
def responder_clase(actor, clase_id, respuesta):
    usuario = bloquear_usuarios_clase({actor.pk}).get(actor.pk)
    usuario = exigir_acceso_clases(usuario)
    clase = _bloquear_clase(clase_id)
    relacion = ClaseAlumno.objects.select_for_update().filter(clase=clase, usuario=usuario).first()
    if relacion is None:
        raise PermissionDenied
    if relacion.estado != "activo" or clase.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se responde una participación activa en una clase Programada.")
    inicio = timezone.make_aware(datetime.combine(clase.evento.turno.fecha, clase.evento.turno.hora_inicio))
    if aplicar_respuesta(relacion, usuario, respuesta, inicio):
        if respuesta == "afirmativa":
            validar_disponibilidad({usuario.pk}, clase.evento.turno.fecha, clase.evento.turno.hora_inicio, clase_id=clase.pk)
        if timezone.now() >= inicio:
            raise ValidationError("La clase alcanzó su inicio. No se modificó la respuesta.")
        with contexto_auditoria(usuario):
            relacion.full_clean()
            relacion.save()
    return relacion
