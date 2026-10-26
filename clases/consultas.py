from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .models import Clase
from .permisos import exigir_acceso_clases, exigir_administracion_clases, puede_dictar_clase


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
