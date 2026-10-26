import hashlib
import json

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno

from .models import Clase, Feriado
from .permisos import exigir_administracion_clases
from .servicios import anular_clase, bloquear_calendario_clases, bloquear_usuarios_clase
from .validaciones import validar_datos_feriado


def consultar_feriados(usuario):
    exigir_administracion_clases(usuario)
    return list(Feriado.objects.order_by("fecha", "pk").values("id", "fecha", "descripcion", "creado_en"))


def _revisar_feriado(fecha, descripcion):
    anula_clases = fecha > timezone.localdate()
    clases = []
    if anula_clases:
        clases = list(Clase.objects.filter(
            evento__tipo=Evento.Tipo.CLASE,
            evento__estado=Evento.Estado.PROGRAMADO,
            evento__turno__fecha=fecha,
        ).select_related("evento__turno__cancha").prefetch_related(
            "profesores", "alumnos",
        ).order_by("pk"))
    instantanea = {
        "fecha": fecha.isoformat(),
        "descripcion": descripcion,
        "anula_clases": anula_clases,
        "clases": [
            [clase.pk, clase.evento_id, clase.evento.turno_id,
             clase.evento.turno.cancha_id, clase.evento.turno.cancha.sede_id,
             clase.evento.turno.hora_inicio.isoformat(), clase.evento.actualizado_en.isoformat(),
             sorted([v.profesor_id, v.estado, v.actualizado_en.isoformat()] for v in clase.profesores.all()),
             sorted([v.usuario_id, v.estado, v.actualizado_en.isoformat()] for v in clase.alumnos.all())]
            for clase in clases
        ],
    }
    huella = hashlib.sha256(json.dumps(instantanea, sort_keys=True).encode()).hexdigest()
    return {
        "fecha": fecha,
        "descripcion": descripcion,
        "anula_clases": anula_clases,
        "clases": clases,
        "huella": huella,
    }


def _usuarios_de_clases(clases):
    usuarios_ids = set()
    for clase in clases:
        usuarios_ids.update(v.profesor_id for v in clase.profesores.all())
        usuarios_ids.update(v.usuario_id for v in clase.alumnos.all())
    return usuarios_ids


def preparar_feriado(usuario, fecha, descripcion):
    usuario = exigir_administracion_clases(usuario)
    validar_datos_feriado(fecha, descripcion)
    if Feriado.objects.filter(fecha=fecha).exists():
        raise ValidationError("Ya existe un feriado registrado para esa fecha.")
    previa = _revisar_feriado(fecha, descripcion.strip())
    previa["confirmacion"] = signing.dumps({
        "usuario": usuario.pk, "huella": previa["huella"],
    }, salt="clases.registrar-feriado", compress=True)
    return previa


@transaction.atomic
def registrar_feriado(usuario, fecha, descripcion, confirmacion=None):
    usuario = exigir_administracion_clases(usuario)
    validar_datos_feriado(fecha, descripcion)
    descripcion = descripcion.strip()
    seleccion = _revisar_feriado(fecha, descripcion)
    usuarios = bloquear_usuarios_clase(_usuarios_de_clases(seleccion["clases"]) | {usuario.pk})
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    bloquear_calendario_clases(fecha)
    if Feriado.objects.filter(fecha=fecha).exists():
        raise ValidationError("Ya existe un feriado registrado para esa fecha.")
    sedes_ids = {clase.evento.turno.cancha.sede_id for clase in seleccion["clases"]}
    canchas_ids = {clase.evento.turno.cancha_id for clase in seleccion["clases"]}
    list(Sede.objects.select_for_update().filter(pk__in=sedes_ids).order_by("pk"))
    list(Cancha.objects.select_for_update().filter(pk__in=canchas_ids).order_by("pk"))
    list(Turno.objects.select_for_update().filter(
        pk__in=[clase.evento.turno_id for clase in seleccion["clases"]],
    ).order_by("pk"))
    list(Evento.objects.select_for_update().filter(
        pk__in=[clase.evento_id for clase in seleccion["clases"]],
    ).order_by("pk"))
    previa = _revisar_feriado(fecha, descripcion)
    if previa["huella"] != seleccion["huella"]:
        raise ValidationError("Las clases cambiaron durante la operación. Revisá nuevamente el feriado.")
    if previa["clases"] or confirmacion is not None:
        if not confirmacion:
            raise ValidationError("Revisá las clases que se anularán antes de confirmar el feriado.")
        try:
            revisado = signing.loads(confirmacion, salt="clases.registrar-feriado")
        except signing.BadSignature:
            raise ValidationError("La confirmación del feriado no es válida. Revisá nuevamente las clases.") from None
        if revisado != {"usuario": usuario.pk, "huella": previa["huella"]}:
            raise ValidationError("La selección del feriado cambió. Revisá nuevamente las clases.")
    with contexto_auditoria(usuario):
        feriado = Feriado.objects.create(fecha=fecha, descripcion=descripcion)
        for clase in previa["clases"]:
            anular_clase(usuario, clase.pk, "Clase anulada por registro de feriado")
        if (fecha > timezone.localdate()) != previa["anula_clases"]:
            raise ValidationError("Cambió la fecha durante la operación. Revisá nuevamente el feriado.")
    return feriado


@transaction.atomic
def quitar_feriado(usuario, feriado_id):
    usuario = exigir_administracion_clases(usuario)
    usuarios = bloquear_usuarios_clase({usuario.pk})
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    inicial = Feriado.objects.get(pk=feriado_id)
    bloquear_calendario_clases(inicial.fecha)
    feriado = Feriado.objects.select_for_update().get(pk=feriado_id)
    if feriado.fecha != inicial.fecha:
        raise ValidationError("La fecha del feriado cambió durante la operación. Revisala nuevamente.")
    with contexto_auditoria(usuario):
        feriado.delete()
    return {"feriado_id": feriado_id, "fecha": inicial.fecha}
