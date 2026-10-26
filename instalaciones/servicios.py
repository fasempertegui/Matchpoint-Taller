import hashlib
import json
from datetime import datetime

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from bloqueos.servicios import anular_bloqueo
from clases.permisos import exigir_administracion_clases
from clases.servicios import anular_clase, bloquear_usuarios_clase
from reservas.models import Evento, Turno
from reservas.servicios import anular_reserva

from .models import Cancha, Sede


def _canchas_de_instalacion(sede, cancha_id, bloquear=False):
    canchas = Cancha.objects.filter(sede=sede).order_by("pk")
    if cancha_id is not None:
        canchas = canchas.filter(pk=cancha_id)
    if bloquear:
        canchas = canchas.select_for_update()
    canchas = list(canchas)
    if cancha_id is not None and not canchas:
        raise Cancha.DoesNotExist
    return canchas


def _revisar_desactivacion(sede, canchas, cancha_id):
    ahora = timezone.localtime()
    eventos = Evento.objects.filter(
        turno__cancha__in=canchas, turno__fecha__gte=ahora.date(),
    ).exclude(estado=Evento.Estado.ANULADO).select_related(
        "turno__cancha", "reserva", "clase", "bloqueo",
    ).prefetch_related("clase__profesores", "clase__alumnos").order_by("turno_id", "pk")
    futuros = []
    for evento in eventos:
        turno = evento.turno
        inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
        fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
        if inicio <= ahora < fin:
            raise ValidationError("No se puede desactivar la instalación mientras tenga actividades en curso.")
        if evento.estado == Evento.Estado.PROGRAMADO and inicio > ahora:
            futuros.append(evento)
    instantanea = {
        "sede": [sede.pk, sede.nombre, sede.estado],
        "cancha": cancha_id,
        "canchas": [[cancha.pk, cancha.nombre, cancha.estado] for cancha in canchas],
        "eventos": [
            [evento.pk, evento.tipo, evento.estado, evento.turno_id,
             evento.turno.cancha_id, evento.turno.fecha.isoformat(), evento.turno.hora_inicio.isoformat(),
             evento.actualizado_en.isoformat()]
            for evento in futuros
        ],
        "asignaciones": [
            [evento.clase.pk,
             sorted([v.profesor_id, v.estado, v.actualizado_en.isoformat()] for v in evento.clase.profesores.all()),
             sorted([v.usuario_id, v.estado, v.actualizado_en.isoformat()] for v in evento.clase.alumnos.all())]
            for evento in futuros if evento.tipo == Evento.Tipo.CLASE
        ],
    }
    huella = hashlib.sha256(json.dumps(instantanea, sort_keys=True).encode()).hexdigest()
    return {
        "sede": sede,
        "cancha": canchas[0] if cancha_id is not None else None,
        "eventos": futuros,
        "huella": huella,
    }


def _usuarios_de_eventos(eventos):
    usuarios_ids = set()
    for evento in eventos:
        if evento.tipo == Evento.Tipo.CLASE:
            usuarios_ids.update(v.profesor_id for v in evento.clase.profesores.all())
            usuarios_ids.update(v.usuario_id for v in evento.clase.alumnos.all())
        elif evento.tipo == Evento.Tipo.RESERVA:
            usuarios_ids.add(evento.reserva.organizador_id)
    return usuarios_ids


def preparar_desactivacion(usuario, sede_id, cancha_id=None):
    usuario = exigir_administracion_clases(usuario)
    sede = Sede.objects.get(pk=sede_id)
    canchas = _canchas_de_instalacion(sede, cancha_id)
    previa = _revisar_desactivacion(sede, canchas, cancha_id)
    previa["confirmacion"] = signing.dumps({
        "usuario": usuario.pk, "sede": sede.pk, "cancha": cancha_id, "huella": previa["huella"],
    }, salt="instalaciones.desactivacion", compress=True)
    return previa


def _validar_confirmacion(confirmacion, usuario, sede_id, cancha_id, huella):
    if not confirmacion:
        raise ValidationError("Revisá las actividades futuras antes de confirmar la desactivación.")
    try:
        seleccion = signing.loads(confirmacion, salt="instalaciones.desactivacion")
    except signing.BadSignature:
        raise ValidationError("La confirmación de desactivación no es válida. Revisá nuevamente las actividades.") from None
    if seleccion != {"usuario": usuario.pk, "sede": sede_id, "cancha": cancha_id, "huella": huella}:
        raise ValidationError("Las actividades o la instalación cambiaron. Revisá nuevamente la desactivación.")


@transaction.atomic
def _cambiar_estado_instalacion(usuario, sede_id, estado, cancha_id=None, confirmacion=None):
    usuario = exigir_administracion_clases(usuario)
    sede = Sede.objects.get(pk=sede_id)
    canchas = _canchas_de_instalacion(sede, cancha_id)
    instalacion = canchas[0] if cancha_id is not None else sede
    if estado not in instalacion.Estado.values:
        raise ValidationError("El estado solicitado para la instalación no es válido.")
    seleccion = None
    if estado == instalacion.Estado.INACTIVA and instalacion.estado != estado:
        seleccion = _revisar_desactivacion(sede, canchas, cancha_id)
    usuarios_ids = {usuario.pk}
    if seleccion is not None:
        usuarios_ids.update(_usuarios_de_eventos(seleccion["eventos"]))
    usuarios = bloquear_usuarios_clase(usuarios_ids)
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    sede = Sede.objects.select_for_update().get(pk=sede_id)
    canchas = _canchas_de_instalacion(sede, cancha_id, bloquear=True)
    instalacion = canchas[0] if cancha_id is not None else sede
    if instalacion.estado == estado:
        return instalacion
    if estado == instalacion.Estado.ACTIVA:
        with contexto_auditoria(usuario):
            instalacion.estado = estado
            instalacion.save(update_fields=["estado", "actualizado_en"])
        return instalacion

    turnos_ids = Evento.objects.filter(
        turno__cancha__in=canchas, turno__fecha__gte=timezone.localdate(),
    ).exclude(estado=Evento.Estado.ANULADO).values("turno_id")
    turnos = list(Turno.objects.select_for_update().filter(pk__in=turnos_ids).order_by("pk"))
    list(Evento.objects.select_for_update().filter(turno__in=turnos).order_by("pk"))
    previa = _revisar_desactivacion(sede, canchas, cancha_id)
    if not _usuarios_de_eventos(previa["eventos"]).issubset(usuarios):
        raise ValidationError("Las actividades cambiaron. Revisá nuevamente la desactivación.")
    if previa["eventos"] or confirmacion is not None:
        _validar_confirmacion(confirmacion, usuario, sede_id, cancha_id, previa["huella"])
    motivo = (
        "Actividad anulada por desactivación de la cancha" if cancha_id is not None
        else "Actividad anulada por desactivación de la sede"
    )
    with contexto_auditoria(usuario):
        for evento in previa["eventos"]:
            if evento.tipo == Evento.Tipo.CLASE:
                anular_clase(usuario, evento.clase.pk, motivo)
            elif evento.tipo == Evento.Tipo.RESERVA:
                anular_reserva(usuario, evento.reserva.pk, motivo)
            else:
                turno = evento.turno
                anular_bloqueo(usuario, evento.bloqueo.pk, motivo, turno.cancha, turno.fecha, turno.hora_inicio)
        instalacion.estado = estado
        instalacion.save(update_fields=["estado", "actualizado_en"])
        ahora = timezone.localtime()
        if any(
            timezone.make_aware(datetime.combine(evento.turno.fecha, evento.turno.hora_inicio)) <= ahora
            for evento in previa["eventos"]
        ):
            raise ValidationError("Un turno alcanzó su inicio. No se guardó la desactivación; revisá nuevamente.")
    return instalacion


def cambiar_estado_sede(usuario, sede_id, estado, confirmacion=None):
    return _cambiar_estado_instalacion(usuario, sede_id, estado, confirmacion=confirmacion)


def cambiar_estado_cancha(usuario, sede_id, cancha_id, estado, confirmacion=None):
    return _cambiar_estado_instalacion(usuario, sede_id, estado, cancha_id=cancha_id, confirmacion=confirmacion)
