from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda, fecha_maxima_feriados
from reservas.models import Evento
from usuarios.models import Rol

from .models import Asistencia, ClaseAlumno, ClaseProfesor, TurnoPlanilla


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
    profesores_actuales=frozenset(), participantes_actuales=frozenset(), requiere_profesor=True,
):
    if requiere_profesor and not profesores_ids:
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


def validar_finalizacion_clase(clase, ahora):
    evento = clase.evento
    if evento.tipo != Evento.Tipo.CLASE or evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden finalizar clases Programadas.")
    turno = evento.turno
    fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
    if ahora < fin:
        raise ValidationError("Sólo se puede finalizar una clase cuando terminó su turno.")


def normalizar_registros_asistencia(registros):
    try:
        filas = list(registros)
    except TypeError:
        raise ValidationError("Indicá una lista de registros de asistencia.") from None
    normalizados = {}
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValidationError("Cada registro de asistencia debe indicar usuario y estado.")
        usuario_id = fila.get("usuario_id")
        if type(usuario_id) is not int or usuario_id <= 0:
            raise ValidationError("Elegí un usuario válido para cada registro de asistencia.")
        if usuario_id in normalizados:
            raise ValidationError("No se puede repetir un usuario en la misma carga de asistencia.")
        estado = fila.get("estado")
        if estado not in Asistencia.Estado.values:
            raise ValidationError("Elegí presente, ausente o sin registrar para cada usuario.")
        observaciones = fila.get("observaciones")
        if observaciones is not None and not isinstance(observaciones, str):
            raise ValidationError("Las observaciones de asistencia deben ser un texto.")
        if observaciones is not None:
            observaciones = observaciones.strip() or None
        normalizados[usuario_id] = {"estado": estado, "observaciones": observaciones}
    return normalizados


def validar_asistencia_clase(clase):
    if clase.evento.tipo != Evento.Tipo.CLASE or clase.evento.estado != Evento.Estado.FINALIZADO:
        raise ValidationError("Sólo se puede registrar o corregir asistencia en clases Finalizadas.")


def validar_periodo_actividad_clases(fecha_desde, fecha_hasta):
    if any(not isinstance(fecha, date) or isinstance(fecha, datetime) for fecha in (fecha_desde, fecha_hasta)):
        raise ValidationError("Indicá fechas válidas para consultar la actividad de clases.")
    if fecha_hasta < fecha_desde:
        raise ValidationError("La fecha final no puede ser anterior a la inicial.")
    if fecha_desde < FECHA_INICIO_OPERACIONES or fecha_hasta > fecha_maxima_agenda():
        raise ValidationError("El período debe estar dentro del calendario operativo de clases.")
    if (fecha_hasta - fecha_desde).days + 1 > 366:
        raise ValidationError("El período de consulta no puede superar 366 días corridos inclusive.")


def validar_retiro_rol_profesor(usuario):
    if ClaseProfesor.objects.filter(
        profesor_id=usuario.pk,
        estado=ClaseProfesor.Estado.ACTIVO,
        clase__evento__estado=Evento.Estado.PROGRAMADO,
    ).exists():
        raise ValidationError(
            "No se puede quitar el rol Profesor mientras el usuario tenga "
            "asignaciones activas como profesor en clases Programadas."
        )


def validar_datos_planilla(dia_semana, hora_inicio, modalidad, observaciones):
    if type(dia_semana) is not int or dia_semana not in TurnoPlanilla.DiaSemana.values:
        raise ValidationError("Elegí un día de la semana entre lunes y domingo.")
    if hora_inicio not in tuple(time(hora) for hora in range(23)):
        raise ValidationError("El turno de planilla debe comenzar en punto entre las 00:00 y las 22:00.")
    if modalidad is not None and modalidad not in TurnoPlanilla.Modalidad.values:
        raise ValidationError("Elegí una modalidad válida para el turno de planilla.")
    if observaciones is not None and not isinstance(observaciones, str):
        raise ValidationError("Las observaciones deben ser un texto.")


def validar_horario_planilla(sede, dia_semana, hora_inicio):
    horario = sede.horarios.filter(dia_semana=dia_semana).first()
    franjas = []
    if horario is not None:
        franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
        if horario.hora_inicio_2 is not None:
            franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
    hora_fin = time(hora_inicio.hour + 1)
    if not any(hora_inicio >= inicio and hora_fin <= fin for inicio, fin in franjas):
        raise ValidationError("El turno de planilla debe quedar íntegramente dentro de una franja de funcionamiento.")


def validar_datos_feriado(fecha, descripcion):
    if not isinstance(fecha, date) or isinstance(fecha, datetime):
        raise ValidationError("Indicá una fecha válida para el feriado.")
    if not FECHA_INICIO_OPERACIONES <= fecha <= fecha_maxima_feriados():
        raise ValidationError("El feriado debe estar entre el 01/08/2026 y cinco años después de hoy, inclusive.")
    if not isinstance(descripcion, str) or not descripcion.strip():
        raise ValidationError("Indicá la descripción del feriado.")
    if len(descripcion.strip()) > 150:
        raise ValidationError("La descripción del feriado no puede superar 150 caracteres.")


def validar_periodo_generacion(fecha_desde, fecha_hasta):
    if any(not isinstance(fecha, date) or isinstance(fecha, datetime) for fecha in (fecha_desde, fecha_hasta)):
        raise ValidationError("Indicá fechas válidas para generar clases.")
    if fecha_hasta < fecha_desde:
        raise ValidationError("La fecha final no puede ser anterior a la inicial.")
    if fecha_desde < FECHA_INICIO_OPERACIONES or fecha_hasta > fecha_maxima_agenda():
        raise ValidationError("El período de generación debe estar dentro del calendario operativo de clases.")
    if (fecha_hasta - fecha_desde).days + 1 > 62:
        raise ValidationError("La generación no puede superar 62 días corridos inclusive.")


def validar_eliminacion_clase_generada(clase):
    if not clase.es_generada:
        raise ValidationError("Sólo se pueden eliminar clases generadas desde la planilla.")
    if clase.evento.tipo != Evento.Tipo.CLASE or clase.evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden eliminar clases generadas que sigan Programadas.")
    if clase.asistencias.exclude(estado=Asistencia.Estado.SIN_REGISTRAR).exists():
        raise ValidationError("No se puede eliminar una clase con asistencia registrada.")
