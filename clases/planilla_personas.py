from collections import Counter
from datetime import time

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from instalaciones.models import Cancha, Sede

from .models import TurnoPlanilla
from .permisos import exigir_administracion_clases
from .planilla import editar_turno_planilla, validar_version_turno_planilla, version_turno_planilla
from .servicios import bloquear_usuarios_clase
from .validaciones import normalizar_usuarios_clase, validar_horario_planilla, validar_usuarios_clase


FUNCIONES = ("profesores", "participantes")
ACCIONES = ("agregar", "quitar")


def _leer_firma(token, salt):
    try:
        return signing.loads(token, salt=salt, max_age=900)
    except (signing.BadSignature, TypeError):
        raise ValidationError("La selección venció o no es válida. Volvé a seleccionar los horarios.") from None


def seleccionar_horarios(usuario, cancha, valores, funcion):
    usuario = exigir_administracion_clases(usuario)
    if funcion not in FUNCIONES or not valores or len(valores) > 161:
        raise ValidationError("Elegí los horarios y la función que querés gestionar.")
    coordenadas = set()
    for valor in valores:
        partes = valor.split("-")
        if len(partes) != 2 or any(not parte.isdecimal() or len(parte) > 2 for parte in partes):
            raise ValidationError("La selección contiene horarios inválidos.")
        dia, hora = map(int, partes)
        if dia not in TurnoPlanilla.DiaSemana.values or hora not in range(23):
            raise ValidationError("La selección contiene horarios inválidos.")
        coordenadas.add((dia, time(hora)))
    if len(coordenadas) != len(valores):
        raise ValidationError("La selección contiene horarios repetidos.")
    turnos = [
        turno for turno in TurnoPlanilla.objects.filter(cancha=cancha).prefetch_related("profesores", "alumnos").order_by("pk")
        if (turno.dia_semana, turno.hora_inicio) in coordenadas
    ]
    if len(turnos) != len(coordenadas):
        raise ValidationError("Todos los horarios seleccionados deben estar creados. Revisá la planilla.")
    token = signing.dumps({
        "usuario": usuario.pk, "cancha": cancha.pk, "funcion": funcion,
        "horarios": [{"id": turno.pk, "version": version_turno_planilla(turno)} for turno in turnos],
    }, salt="clases.planilla.personas.seleccion", compress=True)
    consultar_seleccion(usuario, token)
    return token


def consultar_seleccion(usuario, token):
    usuario = exigir_administracion_clases(usuario)
    datos = _leer_firma(token, "clases.planilla.personas.seleccion")
    if datos["usuario"] != usuario.pk:
        raise ValidationError("La selección no corresponde a tu cuenta.")
    cancha = Cancha.objects.select_related("sede").filter(pk=datos["cancha"]).first()
    if cancha is None or cancha.estado != Cancha.Estado.ACTIVA or cancha.sede.estado != Sede.Estado.ACTIVA:
        raise ValidationError("La sede y la cancha deben estar activas para modificar las asignaciones.")
    versiones = {fila["id"]: fila["version"] for fila in datos["horarios"]}
    turnos = list(TurnoPlanilla.objects.filter(cancha=cancha, pk__in=versiones).prefetch_related(
        "profesores", "alumnos",
    ).order_by("dia_semana", "hora_inicio", "pk"))
    if len(turnos) != len(versiones):
        raise ValidationError("Algún horario ya no existe. Volvé a seleccionar desde la planilla.")
    for turno in turnos:
        validar_version_turno_planilla(turno, versiones[turno.pk])
        validar_horario_planilla(cancha.sede, turno.dia_semana, turno.hora_inicio)
    return {"cancha": cancha, "turnos": turnos, "funcion": datos["funcion"], "versiones": versiones}


def personas_asignadas(turno, funcion):
    return {v.profesor_id for v in turno.profesores.all()} if funcion == "profesores" else {v.usuario_id for v in turno.alumnos.all()}


def calcular_cambios(seleccion, accion, personas_ids, usuarios):
    if accion not in ACCIONES or not personas_ids:
        raise ValidationError("Elegí agregar o quitar y al menos una persona.")
    filas = []
    alcance = Counter()
    for turno in seleccion["turnos"]:
        profesores = personas_asignadas(turno, "profesores")
        participantes = personas_asignadas(turno, "participantes")
        actuales = profesores if seleccion["funcion"] == "profesores" else participantes
        afectados = personas_ids - actuales if accion == "agregar" else personas_ids & actuales
        nuevos = actuales | personas_ids if accion == "agregar" else actuales - personas_ids
        nuevos_profesores = nuevos if seleccion["funcion"] == "profesores" else profesores
        nuevos_participantes = nuevos if seleccion["funcion"] == "participantes" else participantes
        try:
            validar_usuarios_clase(
                usuarios, nuevos_profesores, nuevos_participantes,
                profesores_actuales=profesores, participantes_actuales=participantes,
                exigir_profesor=False, exigir_plan_activo=True,
            )
        except ValidationError as error:
            raise ValidationError([
                f"{turno.get_dia_semana_display()} {turno.hora_inicio:%H:%M}: {mensaje}"
                for mensaje in error.messages
            ]) from None
        alcance.update(afectados)
        filas.append({
            "turno": turno, "cantidad": len(afectados), "profesores_ids": nuevos_profesores,
            "participantes_ids": nuevos_participantes,
        })
    return {
        "filas": filas, "vinculos": sum(alcance.values()),
        "horarios_modificados": sum(bool(fila["cantidad"]) for fila in filas),
    }


@transaction.atomic
def aplicar_cambio_personas(usuario, token, accion, personas_ids):
    personas_ids = normalizar_usuarios_clase(personas_ids)
    seleccion = consultar_seleccion(usuario, token)
    usuarios_ids = personas_ids | {usuario.pk} | {
        pk for turno in seleccion["turnos"] for funcion in FUNCIONES for pk in personas_asignadas(turno, funcion)
    }
    usuarios = bloquear_usuarios_clase(usuarios_ids)
    usuario = exigir_administracion_clases(usuarios.get(usuario.pk))
    sede = Sede.objects.select_for_update().filter(pk=seleccion["cancha"].sede_id).first()
    cancha = Cancha.objects.select_for_update().filter(pk=seleccion["cancha"].pk).first()
    if sede is None or cancha is None:
        raise ValidationError("La sede o la cancha ya no están disponibles. Revisá la selección.")
    list(TurnoPlanilla.objects.select_for_update().filter(pk__in=[t.pk for t in seleccion["turnos"]]).order_by("pk"))
    seleccion = consultar_seleccion(usuario, token)
    if not personas_ids <= usuarios.keys():
        raise ValidationError("Alguna persona ya no está disponible. Revisá la selección.")
    revision = calcular_cambios(seleccion, accion, personas_ids, usuarios)
    for fila in revision["filas"]:
        if fila["cantidad"]:
            turno = fila["turno"]
            editar_turno_planilla(
                usuario, turno.pk, fila["profesores_ids"], fila["participantes_ids"], turno.observaciones,
                version=seleccion["versiones"][turno.pk],
            )
    return revision
