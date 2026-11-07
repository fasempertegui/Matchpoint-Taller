from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone


def aplicar_respuesta(relacion, actor, respuesta, inicio):
    if actor.pk != relacion.usuario_id:
        raise PermissionDenied
    if respuesta not in ("afirmativa", "negativa"):
        raise ValidationError("Elegí una respuesta afirmativa o negativa.")
    if timezone.now() >= inicio:
        raise ValidationError("Sólo se puede responder antes del inicio de la actividad.")
    if relacion.respuesta == respuesta:
        return False
    if relacion.respuesta_modificada_en is not None:
        raise ValidationError("Ya utilizaste el único cambio de respuesta permitido.")
    ahora = timezone.now()
    if relacion.respuesta == "pendiente":
        relacion.respuesta_inicial = respuesta
        relacion.respondido_por = actor
        relacion.respondido_en = ahora
    else:
        relacion.respuesta_modificada_por = actor
        relacion.respuesta_modificada_en = ahora
    relacion.respuesta = respuesta
    return True
