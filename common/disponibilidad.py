from django.core.exceptions import ValidationError
from django.db.models import Q


def reservas_personales(usuario_id, *, excluir=None):
    from reservas.models import Evento, Reserva
    consulta = Reserva.objects.filter(
        Q(organizador_id=usuario_id) | Q(
            invitados__usuario_id=usuario_id, invitados__estado="vigente",
            invitados__respuesta__in=("pendiente", "afirmativa"),
        ), evento__estado=Evento.Estado.PROGRAMADO,
    ).distinct()
    return consulta.exclude(pk=excluir) if excluir is not None else consulta


def personas_ocupadas(usuarios_ids, fecha, hora, *, clase_id=None, reserva_id=None):
    from clases.models import ClaseAlumno, ClaseProfesor
    from reservas.models import Evento, Reserva, ReservaInvitado
    filtros = {"clase__evento__turno__fecha": fecha, "clase__evento__turno__hora_inicio": hora, "estado": "activo"}
    profesores = ClaseProfesor.objects.filter(profesor_id__in=usuarios_ids, **filtros).exclude(
        clase__evento__estado=Evento.Estado.ANULADO,
    ).exclude(clase_id=clase_id)
    alumnos = ClaseAlumno.objects.filter(usuario_id__in=usuarios_ids, **filtros).exclude(
        clase__evento__estado=Evento.Estado.ANULADO,
    ).exclude(clase_id=clase_id)
    reservas = Reserva.objects.filter(
        organizador_id__in=usuarios_ids, evento__turno__fecha=fecha, evento__turno__hora_inicio=hora,
    ).exclude(evento__estado=Evento.Estado.ANULADO).exclude(pk=reserva_id)
    invitados = ReservaInvitado.objects.filter(
        usuario_id__in=usuarios_ids, estado="vigente", respuesta__in=("pendiente", "afirmativa"),
        reserva__evento__turno__fecha=fecha, reserva__evento__turno__hora_inicio=hora,
    ).exclude(reserva__evento__estado=Evento.Estado.ANULADO).exclude(reserva_id=reserva_id)
    return set(profesores.values_list("profesor_id", flat=True)) | set(alumnos.values_list("usuario_id", flat=True)) | set(
        reservas.values_list("organizador_id", flat=True)
    ) | set(invitados.values_list("usuario_id", flat=True))


def validar_disponibilidad(usuarios_ids, fecha, hora, *, clase_id=None, reserva_id=None, controlar_cupo=False):
    if personas_ocupadas(usuarios_ids, fecha, hora, clase_id=clase_id, reserva_id=reserva_id):
        raise ValidationError("Una persona ya participa en otra reserva o clase en esa fecha y hora.", code="persona_ocupada")
    if controlar_cupo:
        for usuario_id in sorted(usuarios_ids):
            if reservas_personales(usuario_id, excluir=reserva_id).count() >= 2:
                raise ValidationError("Cada persona puede integrar como máximo dos reservas Programadas.")
