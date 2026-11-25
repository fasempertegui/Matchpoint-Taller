from datetime import time

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from auditoria.contexto import contexto_auditoria
from instalaciones.models import Cancha, Sede

from .models import TurnoPlanilla, TurnoPlanillaAlumno, TurnoPlanillaProfesor
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
    turnos = TurnoPlanilla.objects.filter(cancha=cancha).prefetch_related(
        "profesores__profesor", "alumnos__usuario",
    ).order_by("dia_semana", "hora_inicio", "pk")
    return {
        "sede": {"id": cancha.sede_id, "nombre": cancha.sede.nombre, "estado": cancha.sede.estado},
        "cancha": {"id": cancha.pk, "nombre": cancha.nombre, "estado": cancha.estado},
        "turnos": [
            {
                "id": turno.pk,
                "version": version_turno_planilla(turno),
                "dia_semana": turno.dia_semana,
                "hora_inicio": turno.hora_inicio,
                "hora_fin": time(turno.hora_inicio.hour + 1),
                "observaciones": turno.observaciones,
                "actualizado_en": turno.actualizado_en,
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
        "profesores": sorted(v.profesor_id for v in turno.profesores.all()),
        "participantes": sorted(v.usuario_id for v in turno.alumnos.all()),
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


def _normalizar_observaciones_planilla(observaciones):
    if isinstance(observaciones, str):
        return observaciones.strip() or None
    return observaciones


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
    profesores_ids=(), participantes_ids=(), observaciones=None,
):
    return registrar_turnos_planilla(
        registrado_por, cancha, [(dia_semana, hora_inicio)],
        profesores_ids, participantes_ids, observaciones,
    )[0]


@transaction.atomic
def registrar_turnos_planilla(
    registrado_por, cancha, turnos, profesores_ids=(), participantes_ids=(),
    observaciones=None,
):
    registrado_por = exigir_administracion_clases(registrado_por)
    turnos = list(turnos)
    if not turnos or len(turnos) > 161 or len(set(turnos)) != len(turnos):
        raise ValidationError("Elegí horarios válidos de la planilla.")
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    observaciones = _normalizar_observaciones_planilla(observaciones)
    for dia, hora in turnos:
        validar_datos_planilla(dia, hora, observaciones)
    usuarios = bloquear_usuarios_clase(profesores_ids | participantes_ids | {registrado_por.pk})
    registrado_por = exigir_administracion_clases(usuarios.get(registrado_por.pk))
    validar_usuarios_clase(usuarios, profesores_ids, participantes_ids, exigir_profesor=False, exigir_plan_activo=True)
    sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    _validar_instalaciones_planilla(sede, cancha)
    ocupados = set(TurnoPlanilla.objects.filter(cancha=cancha).values_list("dia_semana", "hora_inicio"))
    for dia, hora in turnos:
        validar_horario_planilla(sede, dia, hora)
        if (dia, hora) in ocupados:
            raise ValidationError("Ya existe un turno de planilla para esa cancha, día y hora.")
    creados = TurnoPlanilla.objects.bulk_create([
        TurnoPlanilla(cancha=cancha, dia_semana=dia, hora_inicio=hora, observaciones=observaciones)
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
def editar_turno_planilla(usuario, turno_id, profesores_ids, participantes_ids, observaciones, *, version=None):
    usuario = exigir_administracion_clases(usuario)
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    usuario, sede, cancha, turno, usuarios, profesores, participantes = _bloquear_turno_planilla(
        usuario, turno_id, profesores_ids | participantes_ids,
    )
    if version is not None:
        validar_version_turno_planilla(turno, version)
    observaciones = _normalizar_observaciones_planilla(observaciones)
    validar_datos_planilla(turno.dia_semana, turno.hora_inicio, observaciones)
    _validar_instalaciones_planilla(sede, cancha)
    validar_horario_planilla(sede, turno.dia_semana, turno.hora_inicio)
    validar_usuarios_clase(
        usuarios, profesores_ids, participantes_ids,
        profesores_actuales=profesores, participantes_actuales=participantes,
        exigir_profesor=False, exigir_plan_activo=True,
    )
    if (
        profesores == profesores_ids and participantes == participantes_ids
        and turno.observaciones == observaciones
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
        turno.observaciones = observaciones
        turno.save(update_fields=["observaciones", "actualizado_en"])
    return turno


@transaction.atomic
def quitar_turno_planilla(usuario, turno_id, *, version=None):
    usuario = exigir_administracion_clases(usuario)
    usuario, sede, cancha, turno, usuarios, profesores, participantes = _bloquear_turno_planilla(usuario, turno_id)
    if version is not None:
        validar_version_turno_planilla(turno, version)
    with contexto_auditoria(usuario):
        turno.delete()
    return {"turno_id": turno_id}


@transaction.atomic
def quitar_turnos_planilla(usuario, cancha, versiones):
    usuario = exigir_administracion_clases(usuario)
    if not versiones or len(versiones) > 161:
        raise ValidationError("Seleccioná los horarios que querés quitar.")
    turnos = list(TurnoPlanilla.objects.filter(
        cancha=cancha, pk__in=versiones,
    ).prefetch_related("profesores", "alumnos").order_by("pk"))
    if len(turnos) != len(versiones):
        raise ValidationError("La selección cambió. Volvé a seleccionar los horarios.")
    personas = {usuario.pk}
    for turno in turnos:
        validar_version_turno_planilla(turno, versiones[turno.pk])
        personas.update(v.profesor_id for v in turno.profesores.all())
        personas.update(v.usuario_id for v in turno.alumnos.all())
    usuarios = bloquear_usuarios_clase(personas)
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    turnos = list(TurnoPlanilla.objects.select_for_update().filter(
        cancha=cancha, pk__in=versiones,
    ).prefetch_related("profesores", "alumnos").order_by("pk"))
    if len(turnos) != len(versiones):
        raise ValidationError("La selección cambió. Volvé a seleccionar los horarios.")
    for turno in turnos:
        validar_version_turno_planilla(turno, versiones[turno.pk])
    with contexto_auditoria(usuario):
        TurnoPlanilla.objects.filter(cancha=cancha, pk__in=versiones).delete()
    return len(turnos)
