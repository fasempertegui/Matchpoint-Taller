from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bloqueos.servicios import registrar_bloqueo, validar_inicio_bloqueo
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno

from .models import Clase
from .permisos import exigir_administracion_clases
from .servicios import (
    anular_clase, bloquear_usuarios_clase, consultar_edicion_clase, validar_version_clase,
)
from .validaciones import validar_anulacion_clase, validar_horario_clase


def validar_accion_anulacion(clase, bloquear):
    ahora = timezone.localtime()
    validar_anulacion_clase(clase, ahora)
    if bloquear:
        turno = clase.evento.turno
        if turno.cancha.estado != Cancha.Estado.ACTIVA or turno.cancha.sede.estado != Sede.Estado.ACTIVA:
            raise ValidationError("La sede y la cancha deben estar activas para crear el bloqueo.")
        validar_inicio_bloqueo(turno.fecha, turno.hora_inicio, ahora)
        validar_horario_clase(turno.cancha.sede, turno.fecha, turno.hora_inicio)


def preparar_anulacion_clase(usuario, clase_id, motivo, *, bloquear, motivo_bloqueo="", observaciones="", version):
    usuario = exigir_administracion_clases(usuario)
    clase = consultar_edicion_clase(usuario, clase_id)["clase"]
    validar_version_clase(usuario, clase, version)
    validar_accion_anulacion(clase, bloquear)
    return signing.dumps({
        "usuario": usuario.pk, "clase": clase_id, "version": version,
        "motivo": motivo, "bloquear": bloquear,
        "motivo_bloqueo": motivo_bloqueo, "observaciones": observaciones,
    }, salt="clases.anulacion", compress=True)


@transaction.atomic
def confirmar_anulacion_clase(usuario, clase_id, motivo, *, bloquear, motivo_bloqueo="", observaciones="", confirmacion):
    usuario = exigir_administracion_clases(usuario)
    try:
        revision = signing.loads(confirmacion, salt="clases.anulacion", max_age=900)
    except signing.BadSignature:
        raise ValidationError("La revisión venció o no es válida. Revisá la anulación nuevamente.") from None
    if (
        revision["usuario"] != usuario.pk or revision["clase"] != clase_id
        or revision["motivo"] != motivo or revision["bloquear"] != bloquear
        or revision["motivo_bloqueo"] != motivo_bloqueo or revision["observaciones"] != observaciones
    ):
        raise ValidationError("Los datos o la acción cambiaron. Revisá la anulación nuevamente.")
    inicial = Clase.objects.select_related("evento__turno__cancha__sede").get(pk=clase_id)
    usuarios_ids = set(inicial.profesores.values_list("profesor_id", flat=True)) | set(
        inicial.alumnos.values_list("usuario_id", flat=True)
    )
    usuario = exigir_administracion_clases(bloquear_usuarios_clase(usuarios_ids | {usuario.pk}).get(usuario.pk))
    origen = inicial.evento.turno
    sede = Sede.objects.select_for_update().get(pk=origen.cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=origen.cancha_id)
    turno = Turno.objects.select_for_update().get(pk=origen.pk)
    evento = Evento.objects.select_for_update().get(pk=inicial.evento_id)
    clase = Clase.objects.select_for_update().get(pk=clase_id)
    if clase.evento_id != evento.pk or evento.turno_id != turno.pk or cancha.sede_id != sede.pk:
        raise ValidationError("La ubicación de la clase cambió. Revisá su detalle.")
    cancha.sede = sede
    turno.cancha = cancha
    evento.turno = turno
    clase.evento = evento
    validar_version_clase(usuario, clase, revision["version"])
    validar_accion_anulacion(clase, bloquear)
    if bloquear:
        return registrar_bloqueo(
            usuario, cancha, turno.fecha, turno.hora_inicio,
            motivo_bloqueo, observaciones, evento.pk, motivo,
        )
    return anular_clase(usuario, clase.pk, motivo)
