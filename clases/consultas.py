from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .models import Asistencia, Clase, ClaseAlumno, ClaseProfesor
from .permisos import exigir_acceso_clases, exigir_administracion_clases, puede_dictar_clase
from .validaciones import validar_periodo_actividad_clases


def consultar_clase(usuario, clase_id):
    usuario = exigir_acceso_clases(usuario)
    clase = Clase.objects.select_related("evento__turno__cancha__sede").get(
        pk=clase_id,
        evento__tipo=Evento.Tipo.CLASE,
    )
    es_administrador = usuario.tiene_rol(Rol.ADMINISTRADOR)
    es_profesor = puede_dictar_clase(usuario, clase)
    profesores = clase.profesores.select_related("profesor")
    participantes = clase.alumnos.select_related("usuario")
    asistencias = clase.asistencias.select_related("usuario")
    puede_consultar_grupo = es_administrador or es_profesor
    if not puede_consultar_grupo:
        profesores = profesores.filter(profesor=usuario)
        participantes = participantes.filter(usuario=usuario)
        asistencias = asistencias.filter(usuario=usuario)
        if not (profesores.exists() or participantes.exists() or asistencias.exists()):
            raise PermissionDenied

    turno = clase.evento.turno
    ahora = timezone.localtime()
    inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
    fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
    programada = clase.evento.estado == Evento.Estado.PROGRAMADO
    return {
        "id": clase.pk,
        "evento_id": clase.evento_id,
        "fecha": turno.fecha,
        "hora_inicio": turno.hora_inicio,
        "hora_fin": turno.hora_fin,
        "sede": {"id": turno.cancha.sede_id, "nombre": turno.cancha.sede.nombre},
        "cancha": {"id": turno.cancha_id, "nombre": turno.cancha.nombre},
        "estado": clase.evento.estado,
        "modalidad": clase.modalidad,
        "es_generada": clase.es_generada,
        "observaciones": clase.evento.observaciones,
        "turno_planilla_id": clase.turno_planilla_id if puede_consultar_grupo else None,
        "creado_en": clase.evento.creado_en,
        "actualizado_en": clase.evento.actualizado_en,
        "registrado_por_id": clase.evento.registrado_por_id if puede_consultar_grupo else None,
        "anulado_por_id": clase.evento.anulado_por_id if puede_consultar_grupo else None,
        "anulado_en": clase.evento.anulado_en,
        "motivo_anulacion": clase.evento.motivo_anulacion,
        "finalizado_por_id": clase.finalizado_por_id if puede_consultar_grupo else None,
        "finalizado_en": clase.evento.finalizado_en,
        "profesores": [
            {
                "usuario_id": asignacion.profesor_id,
                "nombre": str(asignacion.profesor),
                "estado": asignacion.estado,
            }
            for asignacion in profesores
        ],
        "participantes": [
            {
                "usuario_id": asignacion.usuario_id,
                "nombre": str(asignacion.usuario),
                "estado": asignacion.estado,
                "observaciones": asignacion.observaciones,
            }
            for asignacion in participantes
        ],
        "asistencias": [
            {
                "usuario_id": asistencia.usuario_id,
                "nombre": str(asistencia.usuario),
                "estado": asistencia.estado,
                "observaciones": asistencia.observaciones,
                "registrada_por_id": asistencia.registrada_por_id if puede_consultar_grupo else None,
                "registrada_en": asistencia.registrada_en,
                "actualizado_en": asistencia.actualizado_en,
            }
            for asistencia in asistencias
        ],
        "es_administrador": es_administrador,
        "es_profesor_asignado": es_profesor,
        "puede_editar": es_administrador and programada,
        "puede_cambiar_cancha": es_administrador and programada and ahora < inicio,
        "puede_anular": es_administrador and programada and ahora < inicio,
        "puede_finalizar": puede_consultar_grupo and programada and ahora >= fin,
        "puede_registrar_asistencia": puede_consultar_grupo and clase.evento.estado == Evento.Estado.FINALIZADO,
    }


def _buscar_usuarios(usuarios, busqueda):
    busqueda = busqueda.strip()
    if busqueda:
        usuarios = usuarios.filter(
            Q(first_name__icontains=busqueda)
            | Q(last_name__icontains=busqueda)
            | Q(username__icontains=busqueda)
        )
    return usuarios.order_by("last_name", "first_name", "pk").values(
        "id", "first_name", "last_name", "username",
    )


def consultar_profesores(usuario, busqueda=""):
    exigir_administracion_clases(usuario)
    profesores = Usuario.objects.filter(is_active=True, roles__rol__codigo=Rol.PROFESOR)
    return _buscar_usuarios(profesores, busqueda)


def consultar_participantes(usuario, busqueda="", incluir_todos=False):
    exigir_administracion_clases(usuario)
    participantes = Usuario.objects.filter(is_active=True)
    if not incluir_todos:
        participantes = participantes.filter(roles__rol__codigo=Rol.ALUMNO)
    return _buscar_usuarios(participantes, busqueda)


def consultar_actividad_clases(usuario, fecha_desde, fecha_hasta, usuario_id=None):
    usuario = exigir_acceso_clases(usuario)
    if usuario_id is None:
        usuario_id = usuario.pk
    if type(usuario_id) is not int or usuario_id <= 0:
        raise ValidationError("Elegí un usuario válido para consultar su actividad.")
    if usuario_id != usuario.pk and not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    validar_periodo_actividad_clases(fecha_desde, fecha_hasta)
    titular = Usuario.objects.get(pk=usuario_id)
    profesores = ClaseProfesor.objects.filter(profesor_id=titular.pk)
    participantes = ClaseAlumno.objects.filter(usuario_id=titular.pk)
    asistencias = Asistencia.objects.filter(usuario_id=titular.pk)
    clases = Clase.objects.filter(
        evento__tipo=Evento.Tipo.CLASE,
        evento__turno__fecha__range=(fecha_desde, fecha_hasta),
    ).annotate(
        tiene_docencia=Exists(profesores.filter(clase_id=OuterRef("pk"))),
        tiene_participacion=Exists(participantes.filter(clase_id=OuterRef("pk"))),
        tiene_asistencia=Exists(asistencias.filter(clase_id=OuterRef("pk"))),
    ).filter(
        Q(tiene_docencia=True) | Q(tiene_participacion=True) | Q(tiene_asistencia=True),
    ).select_related("evento__turno__cancha__sede").prefetch_related(
        Prefetch("profesores", queryset=profesores, to_attr="profesores_del_usuario"),
        Prefetch("alumnos", queryset=participantes, to_attr="participaciones_del_usuario"),
        Prefetch("asistencias", queryset=asistencias, to_attr="asistencias_del_usuario"),
    ).order_by("evento__turno__fecha", "evento__turno__hora_inicio", "pk")

    ahora = timezone.localtime()
    actividad = []
    proximas = []
    anuladas = []
    totales = {
        "clases_asignadas": 0,
        "clases_como_profesor": 0,
        "presentes": 0,
        "ausentes": 0,
        "sin_registrar": 0,
        "anuladas": 0,
    }
    for clase in clases:
        profesor = next(iter(clase.profesores_del_usuario), None)
        participante = next(iter(clase.participaciones_del_usuario), None)
        asistencia = next(iter(clase.asistencias_del_usuario), None)
        profesor_activo = profesor is not None and profesor.estado == ClaseProfesor.Estado.ACTIVO
        participante_activo = participante is not None and participante.estado == ClaseAlumno.Estado.ACTIVO
        estado_asistencia = None
        if asistencia is not None:
            estado_asistencia = asistencia.estado
        elif participante_activo:
            estado_asistencia = Asistencia.Estado.SIN_REGISTRAR
        turno = clase.evento.turno
        fila = {
            "id": clase.pk,
            "fecha": turno.fecha,
            "hora_inicio": turno.hora_inicio,
            "hora_fin": turno.hora_fin,
            "sede": {"id": turno.cancha.sede_id, "nombre": turno.cancha.sede.nombre},
            "cancha": {"id": turno.cancha_id, "nombre": turno.cancha.nombre},
            "estado": clase.evento.estado,
            "modalidad": clase.modalidad,
            "es_generada": clase.es_generada,
            "asignacion_profesor": profesor.estado if profesor is not None else None,
            "asignacion_participante": participante.estado if participante is not None else None,
            "asistencia": estado_asistencia,
            "observaciones_asistencia": asistencia.observaciones if asistencia is not None else None,
            "asistencia_registrada_en": asistencia.registrada_en if asistencia is not None else None,
            "asistencia_actualizada_en": asistencia.actualizado_en if asistencia is not None else None,
        }
        if clase.evento.estado == Evento.Estado.ANULADO:
            anuladas.append(fila)
            totales["anuladas"] += 1
            continue
        actividad.append(fila)
        if participante_activo:
            totales["clases_asignadas"] += 1
        if profesor_activo:
            totales["clases_como_profesor"] += 1
        # Una clase aún Programada no acredita asistencia ni ausencia efectiva.
        if clase.evento.estado == Evento.Estado.FINALIZADO:
            if estado_asistencia == Asistencia.Estado.PRESENTE:
                totales["presentes"] += 1
            elif estado_asistencia == Asistencia.Estado.AUSENTE:
                totales["ausentes"] += 1
            elif estado_asistencia == Asistencia.Estado.SIN_REGISTRAR:
                totales["sin_registrar"] += 1
        inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
        if (
            clase.evento.estado == Evento.Estado.PROGRAMADO and inicio > ahora
            and (profesor_activo or participante_activo)
        ):
            proximas.append(fila)
    return {
        "usuario": {"id": titular.pk, "nombre": str(titular)},
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "totales": totales,
        "clases": actividad,
        "proximas": proximas,
        "anuladas": anuladas,
    }
