from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from reservas.models import Evento

from .models import ClaseAlumno
from .permisos import exigir_acceso_clases
from .servicios import _bloquear_clase, bloquear_usuarios_clase


@transaction.atomic
def responder_clase(actor, clase_id, respuesta, *, identidad):
    usuario = bloquear_usuarios_clase({actor.pk}).get(actor.pk)
    usuario = exigir_acceso_clases(usuario)
    clase = _bloquear_clase(clase_id)
    relacion = ClaseAlumno.objects.select_for_update().filter(clase=clase, usuario=usuario).first()
    if relacion is None:
        raise PermissionDenied
    if str(relacion.identidad) != str(identidad):
        raise ValidationError("La asignación cambió. Volvé a abrir el detalle de la clase.")
    if clase.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo podés registrar el aviso con una asignación en una clase Programada.")
    inicio = timezone.make_aware(datetime.combine(clase.evento.turno.fecha, clase.evento.turno.hora_inicio))
    if respuesta != ClaseAlumno.Respuesta.NO_ASISTIRA:
        raise ValidationError("El aviso de no asistencia no se puede modificar.")
    if timezone.now() >= inicio:
        raise ValidationError("Sólo podés registrar el aviso antes del inicio de la clase.")
    if relacion.respuesta != respuesta:
        relacion.respuesta = respuesta
        relacion.respondido_por = usuario
        relacion.respondido_en = timezone.now()
        with contexto_auditoria(usuario):
            relacion.full_clean()
            if timezone.now() >= inicio:
                raise ValidationError("La clase alcanzó su inicio. No se modificó el aviso.")
            relacion.save()
    return relacion
