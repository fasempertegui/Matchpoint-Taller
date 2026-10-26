from django.core.exceptions import ValidationError
from django.db import transaction

from instalaciones.models import Cancha, Sede
from reservas.models import Evento, Turno
from usuarios.models import Rol, Usuario

from .models import Clase, ClaseAlumno, ClaseProfesor
from .permisos import exigir_administracion_clases
from .validaciones import (
    normalizar_usuarios_clase,
    validar_conflictos_clase,
    validar_datos_clase,
    validar_horario_clase,
    validar_usuarios_clase,
)


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

    # La inactivación de cuentas también bloquea primero a los administradores activos.
    list(
        Usuario.objects.select_for_update(of=("self",))
        .filter(pk__in=usuarios_ids, is_active=True, roles__rol__codigo=Rol.ADMINISTRADOR)
        .order_by("pk")
    )
    usuarios = {
        usuario.pk: usuario
        for usuario in Usuario.objects.select_for_update()
        .filter(pk__in=usuarios_ids)
        .order_by("pk")
        .prefetch_related("roles__rol")
    }
    registrado_por = exigir_administracion_clases(usuarios.get(registrado_por.pk))
    validar_usuarios_clase(usuarios, profesores_ids, participantes_ids)
    validar_conflictos_clase(usuarios, profesores_ids, participantes_ids, fecha, hora_inicio)

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
