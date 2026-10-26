from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from usuarios.models import Rol, Usuario

from .models import Asistencia, Clase, ClaseAlumno, ClaseProfesor
from .permisos import exigir_acceso_clases, exigir_administracion_clases, puede_dictar_clase
from .validaciones import (
    normalizar_registros_asistencia,
    normalizar_usuarios_clase,
    validar_anulacion_clase,
    validar_asistencia_clase,
    validar_conflictos_clase,
    validar_datos_clase,
    validar_finalizacion_clase,
    validar_horario_clase,
    validar_usuarios_clase,
)


def bloquear_usuarios_clase(usuarios_ids):
    # La inactivación de cuentas también bloquea primero a los administradores activos.
    list(
        Usuario.objects.select_for_update(of=("self",))
        .filter(pk__in=usuarios_ids, is_active=True, roles__rol__codigo=Rol.ADMINISTRADOR)
        .order_by("pk")
    )
    return {
        usuario.pk: usuario
        for usuario in Usuario.objects.select_for_update()
        .filter(pk__in=usuarios_ids)
        .order_by("pk")
        .prefetch_related("roles__rol")
    }


def bloquear_calendario_clases(fecha):
    # Coordina fechas sin feriado registrado y alcanza todas las sedes.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [734022, fecha.toordinal()])


def _bloquear_clase(clase_id):
    inicial = Clase.objects.select_related("evento").get(pk=clase_id)
    turno = Turno.objects.select_for_update().get(pk=inicial.evento.turno_id)
    evento = Evento.objects.select_for_update().get(pk=inicial.evento_id)
    clase = Clase.objects.select_for_update().get(pk=clase_id)
    if clase.evento_id != inicial.evento_id or evento.turno_id != turno.pk:
        raise ValidationError("La clase cambió durante la operación. Revisá sus datos.")
    evento.turno = turno
    clase.evento = evento
    return clase


@transaction.atomic
def registrar_clase(
    registrado_por,
    cancha,
    fecha,
    hora_inicio,
    profesores_ids,
    participantes_ids=(),
    modalidad=None,
    observaciones="",
):
    registrado_por = exigir_administracion_clases(registrado_por)
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    if modalidad == "":
        modalidad = None
    validar_datos_clase(fecha, hora_inicio, modalidad, observaciones)
    usuarios_ids = profesores_ids | participantes_ids | {registrado_por.pk}

    usuarios = bloquear_usuarios_clase(usuarios_ids)
    registrado_por = exigir_administracion_clases(usuarios.get(registrado_por.pk))
    validar_usuarios_clase(usuarios, profesores_ids, participantes_ids)
    validar_conflictos_clase(usuarios, profesores_ids, participantes_ids, fecha, hora_inicio)
    bloquear_calendario_clases(fecha)

    try:
        sede = Sede.objects.select_for_update().get(pk=cancha.sede_id)
        cancha = Cancha.objects.select_for_update().get(pk=cancha.pk, sede=sede)
    except (Sede.DoesNotExist, Cancha.DoesNotExist):
        raise ValidationError("Elegí una cancha válida de la sede.") from None
    if sede.estado != Sede.Estado.ACTIVA or cancha.estado != Cancha.Estado.ACTIVA:
        raise ValidationError("La sede y la cancha deben estar activas para crear una clase.")
    validar_horario_clase(sede, fecha, hora_inicio)

    turno, _ = Turno.objects.get_or_create(cancha=cancha, fecha=fecha, hora_inicio=hora_inicio)
    turno = Turno.objects.select_for_update().get(pk=turno.pk)
    if Evento.objects.filter(turno=turno).exclude(estado=Evento.Estado.ANULADO).exists():
        raise ValidationError("El turno ya está ocupado por otra actividad.")

    evento = Evento.objects.create(
        turno=turno,
        tipo=Evento.Tipo.CLASE,
        registrado_por=registrado_por,
        observaciones=observaciones.strip(),
    )
    clase = Clase.objects.create(evento=evento, modalidad=modalidad, es_generada=False)
    ClaseProfesor.objects.bulk_create([
        ClaseProfesor(clase=clase, profesor_id=usuario_id)
        for usuario_id in sorted(profesores_ids)
    ])
    ClaseAlumno.objects.bulk_create([
        ClaseAlumno(clase=clase, usuario_id=usuario_id)
        for usuario_id in sorted(participantes_ids)
    ])
    return clase


@transaction.atomic
def editar_clase(
    modificado_por, clase_id, profesores_ids, participantes_ids,
    modalidad, observaciones, cancha=None,
):
    modificado_por = exigir_administracion_clases(modificado_por)
    profesores_ids = normalizar_usuarios_clase(profesores_ids)
    participantes_ids = normalizar_usuarios_clase(participantes_ids)
    inicial = Clase.objects.select_related("evento__turno__cancha").get(pk=clase_id)
    profesores_iniciales = dict(inicial.profesores.values_list("profesor_id", "estado"))
    participantes_iniciales = dict(inicial.alumnos.values_list("usuario_id", "estado"))
    origen = inicial.evento.turno
    destino = cancha if cancha is not None else origen.cancha
    cambia_cancha = destino.pk != origen.cancha_id
    if modalidad == "":
        modalidad = None
    validar_datos_clase(origen.fecha, origen.hora_inicio, modalidad, observaciones)
    observaciones = observaciones.strip()

    usuarios_ids = (
        profesores_ids | participantes_ids | set(profesores_iniciales)
        | set(participantes_iniciales) | {modificado_por.pk}
    )
    usuarios = bloquear_usuarios_clase(usuarios_ids)
    modificado_por = exigir_administracion_clases(usuarios.get(modificado_por.pk))

    sedes = {
        sede.pk: sede
        for sede in Sede.objects.select_for_update()
        .filter(pk__in={origen.cancha.sede_id, destino.sede_id}).order_by("pk")
    }
    canchas = {
        cancha_actual.pk: cancha_actual
        for cancha_actual in Cancha.objects.select_for_update()
        .filter(pk__in={origen.cancha_id, destino.pk}).order_by("pk")
    }
    if (
        origen.cancha_id not in canchas or destino.pk not in canchas
        or canchas[origen.cancha_id].sede_id != origen.cancha.sede_id
        or canchas[destino.pk].sede_id != destino.sede_id
        or origen.cancha.sede_id not in sedes or destino.sede_id not in sedes
    ):
        raise ValidationError("Las instalaciones cambiaron. Revisá la selección de cancha.")
    destino = canchas[destino.pk]
    if cambia_cancha:
        sede_destino = sedes[destino.sede_id]
        if sede_destino.estado != Sede.Estado.ACTIVA or destino.estado != Cancha.Estado.ACTIVA:
            raise ValidationError("La sede y la cancha de destino deben estar activas.")
        validar_horario_clase(sede_destino, origen.fecha, origen.hora_inicio)
        turno_destino, _ = Turno.objects.get_or_create(
            cancha=destino, fecha=origen.fecha, hora_inicio=origen.hora_inicio,
        )
    else:
        turno_destino = origen
    turnos = {
        turno.pk: turno
        for turno in Turno.objects.select_for_update()
        .filter(pk__in={origen.pk, turno_destino.pk}).order_by("pk")
    }
    evento = Evento.objects.select_for_update().get(pk=inicial.evento_id)
    clase = Clase.objects.select_for_update().get(pk=clase_id)
    profesores = dict(clase.profesores.values_list("profesor_id", "estado"))
    participantes = dict(clase.alumnos.values_list("usuario_id", "estado"))
    if (
        clase.evento_id != inicial.evento_id or evento.turno_id != origen.pk
        or evento.actualizado_en != inicial.evento.actualizado_en
        or profesores != profesores_iniciales or participantes != participantes_iniciales
    ):
        raise ValidationError("La clase cambió durante la edición. Revisá sus datos y asignaciones.")
    if evento.tipo != Evento.Tipo.CLASE or evento.estado != Evento.Estado.PROGRAMADO:
        raise ValidationError("Sólo se pueden editar clases Programadas.")
    ahora = timezone.localtime()
    inicio = timezone.make_aware(datetime.combine(origen.fecha, origen.hora_inicio))
    if cambia_cancha:
        if ahora >= inicio:
            raise ValidationError("Sólo se puede cambiar de cancha antes del inicio de la clase.")
        if Evento.objects.filter(turno=turnos[turno_destino.pk]).exclude(
            estado=Evento.Estado.ANULADO,
        ).exists():
            raise ValidationError("El turno de la cancha de destino está ocupado por otra actividad.")

    profesores_activos = {pk for pk, estado in profesores.items() if estado == ClaseProfesor.Estado.ACTIVO}
    participantes_activos = {pk for pk, estado in participantes.items() if estado == ClaseAlumno.Estado.ACTIVO}
    validar_usuarios_clase(
        usuarios, profesores_ids, participantes_ids,
        profesores_actuales=profesores_activos, participantes_actuales=participantes_activos,
    )
    validar_conflictos_clase(
        usuarios, profesores_ids, participantes_ids, origen.fecha, origen.hora_inicio,
        clase_id=clase.pk,
    )
    if (
        not cambia_cancha and clase.modalidad == modalidad and evento.observaciones == observaciones
        and profesores_activos == profesores_ids and participantes_activos == participantes_ids
    ):
        clase.evento = evento
        return clase

    with contexto_auditoria(modificado_por):
        if profesores_activos != profesores_ids:
            clase.profesores.filter(estado=ClaseProfesor.Estado.ACTIVO).exclude(
                profesor_id__in=profesores_ids,
            ).update(estado=ClaseProfesor.Estado.INACTIVO, actualizado_en=ahora)
            clase.profesores.filter(
                estado=ClaseProfesor.Estado.INACTIVO, profesor_id__in=profesores_ids,
            ).update(estado=ClaseProfesor.Estado.ACTIVO, actualizado_en=ahora)
            ClaseProfesor.objects.bulk_create([
                ClaseProfesor(clase=clase, profesor_id=pk)
                for pk in sorted(profesores_ids - set(profesores))
            ])
        if participantes_activos != participantes_ids:
            clase.alumnos.filter(estado=ClaseAlumno.Estado.ACTIVO).exclude(
                usuario_id__in=participantes_ids,
            ).update(estado=ClaseAlumno.Estado.INACTIVO, actualizado_en=ahora)
            clase.alumnos.filter(
                estado=ClaseAlumno.Estado.INACTIVO, usuario_id__in=participantes_ids,
            ).update(estado=ClaseAlumno.Estado.ACTIVO, recordatorio_enviado=False, actualizado_en=ahora)
            ClaseAlumno.objects.bulk_create([
                ClaseAlumno(clase=clase, usuario_id=pk)
                for pk in sorted(participantes_ids - set(participantes))
            ])
        if clase.modalidad != modalidad:
            clase.modalidad = modalidad
            clase.save(update_fields=["modalidad"])
        campos_evento = ["actualizado_en"]
        if evento.observaciones != observaciones:
            evento.observaciones = observaciones
            campos_evento.append("observaciones")
        if cambia_cancha:
            evento.turno = turnos[turno_destino.pk]
            campos_evento.append("turno")
        evento.save(update_fields=campos_evento)
        if cambia_cancha and timezone.localtime() >= inicio:
            raise ValidationError("El turno ya comenzó. No se guardó el cambio de cancha.")
    clase.evento = evento
    return clase


@transaction.atomic
def anular_clase(anulado_por, clase_id, motivo):
    anulado_por = exigir_administracion_clases(anulado_por)
    if not isinstance(motivo, str) or not motivo.strip():
        raise ValidationError("Indicá el motivo de la anulación.")
    motivo = motivo.strip()
    inicial = Clase.objects.select_related("evento__turno__cancha").get(pk=clase_id)
    profesores_ids = set(inicial.profesores.values_list("profesor_id", flat=True))
    participantes_ids = set(inicial.alumnos.values_list("usuario_id", flat=True))
    usuarios = bloquear_usuarios_clase(profesores_ids | participantes_ids | {anulado_por.pk})
    anulado_por = exigir_administracion_clases(usuarios.get(anulado_por.pk))

    origen = inicial.evento.turno
    Sede.objects.select_for_update().get(pk=origen.cancha.sede_id)
    cancha = Cancha.objects.select_for_update().get(pk=origen.cancha_id)
    turno = Turno.objects.select_for_update().get(pk=origen.pk)
    evento = Evento.objects.select_for_update().get(pk=inicial.evento_id)
    clase = Clase.objects.select_for_update().get(pk=clase_id)
    if (
        cancha.sede_id != origen.cancha.sede_id
        or clase.evento_id != inicial.evento_id or evento.turno_id != origen.pk
        or evento.actualizado_en != inicial.evento.actualizado_en
        or profesores_ids != set(clase.profesores.values_list("profesor_id", flat=True))
        or participantes_ids != set(clase.alumnos.values_list("usuario_id", flat=True))
    ):
        raise ValidationError("La clase cambió durante la anulación. Revisá sus datos y asignaciones.")
    evento.turno = turno
    clase.evento = evento
    ahora = timezone.localtime()
    validar_anulacion_clase(clase, ahora)

    with contexto_auditoria(anulado_por):
        evento.estado = Evento.Estado.ANULADO
        evento.anulado_por = anulado_por
        evento.anulado_en = ahora
        evento.motivo_anulacion = motivo
        evento.save(update_fields=[
            "estado", "anulado_por", "anulado_en", "motivo_anulacion", "actualizado_en",
        ])
        inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
        if timezone.localtime() >= inicio:
            raise ValidationError("El turno ya comenzó. No se guardó la anulación.")
    return clase


@transaction.atomic
def finalizar_clase(clase_id, usuario=None):
    if usuario is not None:
        usuario = exigir_acceso_clases(usuario)
        usuarios = bloquear_usuarios_clase({usuario.pk})
        usuario = exigir_acceso_clases(usuarios.get(usuario.pk))

    clase = _bloquear_clase(clase_id)
    evento = clase.evento
    if usuario is not None and not (
        usuario.tiene_rol(Rol.ADMINISTRADOR) or puede_dictar_clase(usuario, clase)
    ):
        raise PermissionDenied
    ahora = timezone.localtime()
    validar_finalizacion_clase(clase, ahora)

    with contexto_auditoria(usuario, origen="aplicacion" if usuario is not None else "tarea"):
        evento.estado = Evento.Estado.FINALIZADO
        evento.finalizado_en = ahora
        evento.save(update_fields=["estado", "finalizado_en", "actualizado_en"])
        responsable_id = usuario.pk if usuario is not None else None
        if clase.finalizado_por_id != responsable_id:
            clase.finalizado_por = usuario
            clase.save(update_fields=["finalizado_por"])
    return clase


def finalizar_clases_vencidas():
    limite_inicio = timezone.localtime() - timedelta(hours=1)
    pendientes = Clase.objects.filter(
        evento__tipo=Evento.Tipo.CLASE,
        evento__estado=Evento.Estado.PROGRAMADO,
    ).filter(
        Q(evento__turno__fecha__lt=limite_inicio.date())
        | Q(evento__turno__fecha=limite_inicio.date(), evento__turno__hora_inicio__lte=limite_inicio.time())
    ).order_by("pk").values_list("pk", flat=True)

    finalizadas = 0
    for clase_id in pendientes.iterator(chunk_size=500):
        try:
            finalizar_clase(clase_id)
        except (ValidationError, Clase.DoesNotExist, Evento.DoesNotExist):
            continue
        else:
            finalizadas += 1
    return finalizadas


@transaction.atomic
def registrar_asistencia(usuario, clase_id, registros, finalizar=False):
    usuario = exigir_acceso_clases(usuario)
    if not isinstance(finalizar, bool):
        raise ValidationError("Indicá si corresponde finalizar la clase junto con la asistencia.")
    registros = normalizar_registros_asistencia(registros)
    usuarios = bloquear_usuarios_clase(set(registros) | {usuario.pk})
    usuario = exigir_acceso_clases(usuarios.get(usuario.pk))
    if set(registros) - usuarios.keys():
        raise ValidationError("Todos los usuarios de la asistencia deben existir.")
    clase = _bloquear_clase(clase_id)
    if not (usuario.tiene_rol(Rol.ADMINISTRADOR) or puede_dictar_clase(usuario, clase)):
        raise PermissionDenied

    with contexto_auditoria(usuario):
        if finalizar and clase.evento.estado == Evento.Estado.PROGRAMADO:
            clase = finalizar_clase(clase.pk, usuario=usuario)
        validar_asistencia_clase(clase)
        asistencias = {
            asistencia.usuario_id: asistencia
            for asistencia in clase.asistencias.select_for_update()
            .filter(usuario_id__in=registros).order_by("usuario_id")
        }
        ahora = timezone.localtime()
        hubo_cambios = False
        for usuario_id, datos in sorted(registros.items()):
            asistencia = asistencias.get(usuario_id)
            if asistencia is not None and (
                asistencia.estado == datos["estado"]
                and asistencia.observaciones == datos["observaciones"]
            ):
                continue
            hubo_cambios = True
            sin_registrar = datos["estado"] == Asistencia.Estado.SIN_REGISTRAR
            if asistencia is None:
                Asistencia.objects.create(
                    clase=clase,
                    usuario_id=usuario_id,
                    estado=datos["estado"],
                    observaciones=datos["observaciones"],
                    registrada_por=None if sin_registrar else usuario,
                    registrada_en=None if sin_registrar else ahora,
                )
            else:
                asistencia.estado = datos["estado"]
                asistencia.observaciones = datos["observaciones"]
                asistencia.registrada_por = None if sin_registrar else usuario
                asistencia.registrada_en = None if sin_registrar else ahora
                asistencia.save(update_fields=[
                    "estado", "observaciones", "registrada_por", "registrada_en", "actualizado_en",
                ])
        if hubo_cambios:
            clase.evento.save(update_fields=["actualizado_en"])
    return clase
