from datetime import time

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno

from .models import Clase, TurnoPlanilla, TurnoPlanillaAlumno, TurnoPlanillaProfesor
from .permisos import exigir_administracion_clases
from .servicios import bloquear_usuarios_clase
from .validaciones import (
    normalizar_usuarios_clase,
    validar_datos_planilla,
    validar_horario_planilla,
    validar_usuarios_clase,
)


def consultar_planilla(usuario, sede_id, cancha_id):
    exigir_administracion_clases(usuario)
    cancha = Cancha.objects.select_related("sede").get(pk=cancha_id, sede_id=sede_id)
    turnos = TurnoPlanilla.objects.filter(cancha=cancha).annotate(
        clases_vinculadas=Count("clases"),
    ).prefetch_related("profesores__profesor", "alumnos__usuario").order_by("dia_semana", "hora_inicio", "pk")
    return {
        "sede": {"id": cancha.sede_id, "nombre": cancha.sede.nombre, "estado": cancha.sede.estado},
        "cancha": {"id": cancha.pk, "nombre": cancha.nombre, "estado": cancha.estado},
        "turnos": [
            {
                "id": turno.pk,
                "dia_semana": turno.dia_semana,
                "hora_inicio": turno.hora_inicio,
                "hora_fin": time(turno.hora_inicio.hour + 1),
                "modalidad": turno.modalidad,
                "observaciones": turno.observaciones,
                "actualizado_en": turno.actualizado_en,
                "clases_vinculadas": turno.clases_vinculadas,
                "profesores": [
                    {"usuario_id": vinculo.profesor_id, "nombre": str(vinculo.profesor)}
                    for vinculo in turno.profesores.all()
                ],
                "participantes": [
                    {"usuario_id": vinculo.usuario_id, "nombre": str(vinculo.usuario)}
                    for vinculo in turno.alumnos.all()
                ],
            }
            for turno in turnos
        ],
    }


def _datos_version_planilla(turno):
    return {
        "id": turno.pk,
        "cancha": turno.cancha_id,
        "dia": turno.dia_semana,
        "hora": turno.hora_inicio.isoformat(),
        "actualizado_en": turno.actualizado_en.isoformat(),
        "profesores": sorted(turno.profesores.values_list("profesor_id", flat=True)),
        "participantes": sorted(turno.alumnos.values_list("usuario_id", flat=True)),
    }


def version_turno_planilla(turno):
    return signing.dumps(_datos_version_planilla(turno), salt="clases.planilla.version", compress=True)


def validar_version_turno_planilla(turno, version):
    try:
        datos = signing.loads(version, salt="clases.planilla.version", max_age=900)
    except signing.BadSignature:
        raise ValidationError("La revisión venció o no es válida. Abrí nuevamente el horario de la planilla.") from None
    if datos != _datos_version_planilla(turno):
        raise ValidationError("El horario de la planilla cambió. Abrilo nuevamente antes de continuar.")


def _normalizar_datos_planilla(modalidad, observaciones):
    if modalidad == "":
        modalidad = None
    if isinstance(observaciones, str):
        observaciones = observaciones.strip() or None
    return modalidad, observaciones


def _validar_instalaciones_planilla(sede, cancha):
    if sede.estado != Sede.Estado.ACTIVA or cancha.estado != Cancha.Estado.ACTIVA:
        raise ValidationError("La sede y la cancha deben estar activas para guardar la planilla.")


def _bloquear_turno_planilla(usuario, turno_id, usuarios_nuevos=frozenset()):
    inicial = TurnoPlanilla.objects.select_related("cancha").get(pk=turno_id)
    profesores = set(inicial.profesores.values_list("profesor_id", flat=True))
    participantes = set(inicial.alumnos.values_list("usuario_id", flat=True))
    usuarios = bloquear_usuarios_clase(profesores | participantes | usuarios_nuevos | {usuario.pk})
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    sede = Sede.objects.select_for_update().get(pk=inicial.cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=inicial.cancha_id, sede=sede)
    turno = TurnoPlanilla.objects.select_for_update().get(pk=turno_id)
    if (
        (turno.cancha_id, turno.dia_semana, turno.hora_inicio, turno.actualizado_en)
        != (inicial.cancha_id, inicial.dia_semana, inicial.hora_inicio, inicial.actualizado_en)
        or profesores != set(turno.profesores.values_list("profesor_id", flat=True))
        or participantes != set(turno.alumnos.values_list("usuario_id", flat=True))
    ):
        raise ValidationError("El turno de planilla cambió durante la operación. Revisá sus datos.")
    return usuario, sede, cancha, turno, usuarios, profesores, participantes


def registrar_turno_planilla(
    registrado_por, cancha, dia_semana, hora_inicio,
    profesores_ids=(), participantes_ids=(), modalidad=None, observaciones=None,
):
    return registrar_turnos_planilla(
        registrado_por, cancha, [(dia_semana, hora_inicio)],
        profesores_ids, participantes_ids, modalidad, observaciones,
    )[0]


@transaction.atomic
def registrar_turnos_planilla(
    registrado_por, cancha, turnos, profesores_ids=(), participantes_ids=(),
    modalidad=None, observaciones=None,
):
    registrado_por = exigir_administracion_clases(registrado_por)
    turnos = list(turnos)
    if not turnos or len(turnos) > 161 or len(set(turnos)) != len(turnos):
        raise ValidationError("Elegí horarios válidos de la planilla.")
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    modalidad, observaciones = _normalizar_datos_planilla(modalidad, observaciones)
    for dia, hora in turnos:
        validar_datos_planilla(dia, hora, modalidad, observaciones)
    usuarios = bloquear_usuarios_clase(profesores_ids | participantes_ids | {registrado_por.pk})
    registrado_por = exigir_administracion_clases(usuarios.get(registrado_por.pk))
    validar_usuarios_clase(usuarios, profesores_ids, participantes_ids, requiere_profesor=False)
    sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    _validar_instalaciones_planilla(sede, cancha)
    ocupados = set(TurnoPlanilla.objects.filter(cancha=cancha).values_list("dia_semana", "hora_inicio"))
    for dia, hora in turnos:
        validar_horario_planilla(sede, dia, hora)
        if (dia, hora) in ocupados:
            raise ValidationError("Ya existe un turno de planilla para esa cancha, día y hora.")
    creados = TurnoPlanilla.objects.bulk_create([
        TurnoPlanilla(cancha=cancha, dia_semana=dia, hora_inicio=hora, modalidad=modalidad, observaciones=observaciones)
        for dia, hora in sorted(turnos)
    ])
    TurnoPlanillaProfesor.objects.bulk_create([
        TurnoPlanillaProfesor(turno_planilla=turno, profesor_id=pk)
        for turno in creados for pk in sorted(profesores_ids)
    ])
    TurnoPlanillaAlumno.objects.bulk_create([
        TurnoPlanillaAlumno(turno_planilla=turno, usuario_id=pk)
        for turno in creados for pk in sorted(participantes_ids)
    ])
    return creados


@transaction.atomic
def editar_turno_planilla(usuario, turno_id, profesores_ids, participantes_ids, modalidad, observaciones, *, version=None):
    usuario = exigir_administracion_clases(usuario)
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    usuario, sede, cancha, turno, usuarios, profesores, participantes = _bloquear_turno_planilla(
        usuario, turno_id, profesores_ids | participantes_ids,
    )
    if version is not None:
        validar_version_turno_planilla(turno, version)
    modalidad, observaciones = _normalizar_datos_planilla(modalidad, observaciones)
    validar_datos_planilla(turno.dia_semana, turno.hora_inicio, modalidad, observaciones)
    _validar_instalaciones_planilla(sede, cancha)
    validar_horario_planilla(sede, turno.dia_semana, turno.hora_inicio)
    validar_usuarios_clase(usuarios, profesores_ids, participantes_ids, requiere_profesor=False)
    if (
        profesores == profesores_ids and participantes == participantes_ids
        and turno.modalidad == modalidad and turno.observaciones == observaciones
    ):
        return turno
    with contexto_auditoria(usuario):
        turno.profesores.exclude(profesor_id__in=profesores_ids).delete()
        turno.alumnos.exclude(usuario_id__in=participantes_ids).delete()
        TurnoPlanillaProfesor.objects.bulk_create([
            TurnoPlanillaProfesor(turno_planilla=turno, profesor_id=pk)
            for pk in sorted(profesores_ids - profesores)
        ])
        TurnoPlanillaAlumno.objects.bulk_create([
            TurnoPlanillaAlumno(turno_planilla=turno, usuario_id=pk)
            for pk in sorted(participantes_ids - participantes)
        ])
        turno.modalidad = modalidad
        turno.observaciones = observaciones
        turno.save(update_fields=["modalidad", "observaciones", "actualizado_en"])
    return turno


@transaction.atomic
def quitar_turno_planilla(usuario, turno_id, *, version=None):
    usuario = exigir_administracion_clases(usuario)
    usuario, sede, cancha, turno, usuarios, profesores, participantes = _bloquear_turno_planilla(usuario, turno_id)
    if version is not None:
        validar_version_turno_planilla(turno, version)
    referencias = list(Clase.objects.filter(turno_planilla=turno).values_list("pk", "evento_id", "evento__turno_id"))
    list(Turno.objects.select_for_update().filter(pk__in=[r[2] for r in referencias]).order_by("pk"))
    list(Evento.objects.select_for_update().filter(pk__in=[r[1] for r in referencias]).order_by("pk"))
    clases = list(
        Clase.objects.select_for_update(of=("self",)).select_related("evento")
        .filter(turno_planilla=turno).order_by("pk")
    )
    actuales = {(clase.pk, clase.evento_id, clase.evento.turno_id) for clase in clases}
    if actuales != set(referencias):
        raise ValidationError("Las clases vinculadas cambiaron. Revisá nuevamente el turno de planilla.")
    with contexto_auditoria(usuario):
        turno.delete()
        if referencias:
            Evento.objects.filter(pk__in=[r[1] for r in referencias]).update(actualizado_en=timezone.now())
    return {"turno_id": turno_id, "clases_desvinculadas": len(referencias)}
