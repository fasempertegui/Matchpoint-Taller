from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from common.bloqueos import bloquear_usuarios
from membresias.continuidad import ZONA_SALTA
from reservas.models import Evento, Reserva
from clases.models import Clase

from .actividades import datos_turno, participacion
from .models import EnvioEmail
from .servicios import encolar_email
from django.urls import reverse


def _candidatos(tipo):
    ahora = timezone.now()
    limite = timezone.localtime(ahora + timedelta(hours=1), ZONA_SALTA)
    hoy = timezone.localtime(ahora, ZONA_SALTA).date()
    return Evento.objects.filter(tipo=tipo, estado=Evento.Estado.PROGRAMADO, turno__fecha__range=(hoy, limite.date())).filter(
        Q(turno__fecha__lt=limite.date()) | Q(turno__hora_inicio__lte=limite.time()),
    ).order_by('pk').values_list('pk', flat=True)


def _cubierto(clave, usuario_id, referencia=None, reserva_id=None):
    if EnvioEmail.objects.filter(clave=clave).exists():
        return True
    previos = EnvioEmail.objects.filter(datos__vigencia__usuario_id=usuario_id).exclude(estado=EnvioEmail.Estado.DESCARTADO)
    if referencia:
        if previos.filter(tipo__in=('asignacion_clase', 'invitacion'), datos__vigencia__participacion=referencia,
                          datos__vigencia__cubre_recordatorio=True).exists():
            return True
        if referencia['tipo'] == 'profesor':
            return previos.filter(tipo='generacion_clases', datos__vigencia__clases_generadas__contains=[{
                'clase_id': referencia['actividad_id'], 'identidad': referencia['identidad'], 'cubre_recordatorio': True,
            }]).exists()
        return False
    return previos.filter(tipo='reserva_creada', datos__vigencia__reserva_id=reserva_id,
                          datos__vigencia__cubre_recordatorio=True).exists()


def _encolar(actividad, usuario, funcion, relacion=None):
    if not usuario.esta_habilitado:
        return 0
    es_clase = isinstance(actividad, Clase)
    tipo = 'recordatorio_clase' if es_clase else 'recordatorio_reserva'
    referencia = participacion(relacion, funcion) if relacion else None
    identidad = str(relacion.identidad) if relacion else f'{actividad.pk}:organizador'
    clave = f'{tipo}:{funcion}:{identidad}'
    if _cubierto(clave, usuario.pk, referencia, None if es_clase else actividad.pk):
        return 0
    texto = 'Tu clase comienza dentro de una hora.' if es_clase else 'Tu reserva comienza dentro de una hora.'
    if funcion == 'invitado':
        texto = texto_recordatorio_invitado(relacion.respuesta)
    vigencia = {'usuario_id': usuario.pk, 'evento_id': actividad.evento_id}
    if referencia:
        vigencia['participacion'] = referencia
    if not es_clase:
        vigencia['reserva_id'] = actividad.pk
    ruta = 'clases:clase_detalle' if es_clase else 'reservas:reserva_detalle'
    encolar_email(clave=clave, tipo=tipo, destinatario=usuario.email,
                  datos={'vigencia': vigencia, 'mensaje': {'parrafos': [texto], 'datos': datos_turno(actividad),
                         'acciones': [{'texto': 'Ver actividad', 'ruta': reverse(ruta, args=[actividad.pk])}]}})
    return 1


def texto_recordatorio_invitado(respuesta):
    return ('Todavía no respondiste la invitación a esta reserva. Ingresá para responder antes del inicio.'
            if respuesta == 'pendiente' else 'La reserva a la que confirmaste tu asistencia comienza dentro de una hora.')


@transaction.atomic
def _procesar(evento_id, es_clase):
    modelo = Clase if es_clase else Reserva
    actividad = modelo.objects.select_related('evento__turno__cancha__sede').get(evento_id=evento_id)
    if es_clase:
        ids = set(actividad.profesores.values_list('profesor_id', flat=True)) | set(actividad.alumnos.values_list('usuario_id', flat=True))
    else:
        ids = {actividad.organizador_id} | set(actividad.invitados.values_list('usuario_id', flat=True))
    usuarios = bloquear_usuarios(ids)
    evento = Evento.objects.select_for_update().select_related('turno__cancha__sede').get(pk=evento_id)
    inicio = datetime.combine(evento.turno.fecha, evento.turno.hora_inicio, tzinfo=ZONA_SALTA)
    if evento.estado != Evento.Estado.PROGRAMADO or not timezone.now() < inicio <= timezone.now()+timedelta(hours=1):
        return 0
    actividad.evento = evento
    cantidad = 0
    if es_clase:
        for relacion in actividad.profesores.all():
            if relacion.profesor_id in usuarios:
                cantidad += _encolar(actividad, usuarios[relacion.profesor_id], 'profesor', relacion)
        for relacion in actividad.alumnos.filter(respuesta='asistira'):
            if relacion.usuario_id in usuarios:
                cantidad += _encolar(actividad, usuarios[relacion.usuario_id], 'participante', relacion)
    else:
        cantidad += _encolar(actividad, usuarios[actividad.organizador_id], 'organizador')
        for relacion in actividad.invitados.exclude(respuesta='negativa'):
            if relacion.usuario_id in usuarios:
                cantidad += _encolar(actividad, usuarios[relacion.usuario_id], 'invitado', relacion)
    return cantidad


def encolar_recordatorios_clases():
    return sum(_procesar(pk, True) for pk in _candidatos(Evento.Tipo.CLASE))


def encolar_recordatorios_reservas():
    return sum(_procesar(pk, False) for pk in _candidatos(Evento.Tipo.RESERVA))
