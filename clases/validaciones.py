from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda
from reservas.models import Evento
from usuarios.models import Rol

from .models import ClaseAlumno, ClaseProfesor, TurnoPlanilla


def normalizar_usuarios_clase(identificadores):
    try:
        identificadores = set(identificadores)
    except TypeError:
        raise ValidationError("Elegí usuarios válidos para la clase.") from None
    if any(type(identificador) is not int or identificador <= 0 for identificador in identificadores):
        raise ValidationError("Elegí usuarios válidos para la clase.")
    return identificadores


def validar_datos_clase(fecha, hora_inicio, modalidad, observaciones):
    if not isinstance(fecha, date) or isinstance(fecha, datetime):
        raise ValidationError("Indicá una fecha válida para la clase.")
    if not FECHA_INICIO_OPERACIONES <= fecha <= fecha_maxima_agenda():
        raise ValidationError("La fecha debe estar entre el 01/08/2026 y un año después de hoy, inclusive.")
    if hora_inicio not in tuple(time(hora) for hora in range(23)):
        raise ValidationError("La clase debe comenzar en punto entre las 00:00 y las 22:00.")
    if modalidad is not None and modalidad not in TurnoPlanilla.Modalidad.values:
        raise ValidationError("Elegí una modalidad válida para la clase.")
    if not isinstance(observaciones, str):
        raise ValidationError("Las observaciones deben ser un texto.")


def validar_horario_clase(sede, fecha, hora_inicio):
    horario = sede.horarios.filter(dia_semana=fecha.isoweekday()).first()
    franjas = []
    if horario is not None:
        franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
        if horario.hora_inicio_2 is not None:
            franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
    hora_fin = (datetime.combine(fecha, hora_inicio) + timedelta(hours=1)).time()
    if not any(hora_inicio >= inicio and hora_fin <= fin for inicio, fin in franjas):
        raise ValidationError("La clase debe quedar íntegramente dentro de una franja de funcionamiento de la sede.")


def validar_usuarios_clase(
    usuarios, profesores_ids, participantes_ids,
    profesores_actuales=frozenset(), participantes_actuales=frozenset(),
):
    if not profesores_ids:
        raise ValidationError("La clase debe tener al menos un profesor.")
    if profesores_ids & participantes_ids:
        raise ValidationError("Una persona no puede dictar y participar en la misma clase.")
    nuevos_profesores = profesores_ids - profesores_actuales
    nuevos_participantes = participantes_ids - participantes_actuales
    for usuario_id in sorted(nuevos_profesores | nuevos_participantes):
        usuario = usuarios.get(usuario_id)
        if usuario is None or not usuario.is_active:
            raise ValidationError("Todos los profesores y participantes deben tener una cuenta activa.")
        if usuario_id in profesores_ids and not any(
            asignacion.rol.codigo == Rol.PROFESOR for asignacion in usuario.roles.all()
        ):
            raise ValidationError(f"{usuario} no tiene el rol Profesor.")


def validar_conflictos_clase(usuarios, profesores_ids, participantes_ids, fecha, hora_inicio, clase_id=None):
    usuarios_ids = profesores_ids | participantes_ids
    profesores_ocupados = ClaseProfesor.objects.filter(
        profesor_id__in=usuarios_ids,
        estado=ClaseProfesor.Estado.ACTIVO,
        clase__evento__turno__fecha=fecha,
        clase__evento__turno__hora_inicio=hora_inicio,
    ).exclude(clase__evento__estado=Evento.Estado.ANULADO)
    participantes_ocupados = ClaseAlumno.objects.filter(
        usuario_id__in=usuarios_ids,
        estado=ClaseAlumno.Estado.ACTIVO,
        clase__evento__turno__fecha=fecha,
        clase__evento__turno__hora_inicio=hora_inicio,
    ).exclude(clase__evento__estado=Evento.Estado.ANULADO)
    if clase_id is not None:
        profesores_ocupados = profesores_ocupados.exclude(clase_id=clase_id)
        participantes_ocupados = participantes_ocupados.exclude(clase_id=clase_id)
    ocupados = set(profesores_ocupados.values_list("profesor_id", flat=True)) | set(
        participantes_ocupados.values_list("usuario_id", flat=True)
    )
    if ocupados:
        nombres = ", ".join(str(usuarios[usuario_id]) for usuario_id in sorted(ocupados))
        raise ValidationError(f"Ya tienen otra clase asignada en esa fecha y hora: {nombres}.")


def validar_anulacion_clase(clase, ahora):
    evento = clase.evento
    if evento.tipo != Evento.Tipo.CLASE or evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden anular clases Programadas.")
    turno = evento.turno
    inicio = datetime.combine(turno.fecha, turno.hora_inicio)
    if timezone.make_aware(inicio) <= ahora:
        raise ValidationError("Sólo se puede anular una clase antes del inicio de su turno.")
