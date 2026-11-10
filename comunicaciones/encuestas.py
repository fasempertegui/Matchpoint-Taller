from calendar import monthrange
from datetime import datetime, time, timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from common.bloqueos import bloquear_usuarios
from membresias.continuidad import MODELOS_CONTINUIDAD, ZONA_SALTA, encuesta_abierta, ventana_continuidad
from membresias.fechas import mes_siguiente

from .models import EnvioEmail
from .servicios import encolar_email


def campana_del_dia():
    ahora = timezone.localtime(timezone.now(), ZONA_SALTA)
    if ahora.hour < 9:
        return None
    dia = ahora.date()
    if dia.day == 25:
        return dia, dia.replace(day=1), 'apertura'
    if dia.day == monthrange(dia.year, dia.month)[1]:
        return dia, dia.replace(day=1), 'recordatorio'
    if dia.day == 5:
        return dia, (dia.replace(day=1)-timedelta(days=1)).replace(day=1), 'ultimo_dia'
    return None


def apertura_cubierta(tipo, contrato):
    return EnvioEmail.objects.filter(
        tipo='contratacion', datos__vigencia__contratacion={'tipo': tipo, 'id': contrato.pk},
        datos__vigencia__incluye_encuesta=True,
    ).exclude(estado=EnvioEmail.Estado.DESCARTADO).exists()


@transaction.atomic
def _encolar_para_titular(usuario_id, campana):
    usuario = bloquear_usuarios({usuario_id}).get(usuario_id)
    if usuario is None or not usuario.esta_habilitado or campana_del_dia() != campana:
        return 0
    fecha, mes, aviso = campana
    clave = f'continuidad:{usuario.pk}:{fecha.isoformat()}'
    if EnvioEmail.objects.filter(clave=clave).exists():
        return 0
    referencias, apartados = [], []
    for tipo, modelo in MODELOS_CONTINUIDAD.items():
        contratos = modelo.objects.select_for_update(of=('self',)).select_related(tipo).filter(usuario=usuario, mes_cubierto=mes).exclude(estado='anulado')
        for contrato in contratos:
            if not encuesta_abierta(contrato) or (aviso != 'apertura' and contrato.respuesta_continuidad):
                continue
            if aviso == 'apertura' and apertura_cubierta(tipo, contrato):
                continue
            _, cierre = ventana_continuidad(mes)
            referencias.append({'tipo': tipo, 'id': contrato.pk, 'aviso': aviso})
            texto = ('Hoy es el último día para responder, hasta terminar el día.' if aviso == 'ultimo_dia' else
                     f'Podés responder hasta el 5 de {date_format(cierre, "F")}, inclusive.')
            apartados.append({'titulo': contrato.producto.nombre,
                              'parrafos': [f'Continuidad para {date_format(mes_siguiente(mes), "F Y")}.', texto],
                              'acciones': [{'texto': 'Responder mi encuesta', 'ruta': reverse(f'membresias:mi_{tipo}_contratado', args=[contrato.pk])}]})
    if not referencias:
        return 0
    fin = datetime.combine(fecha+timedelta(days=1), time.min, tzinfo=ZONA_SALTA)
    texto = 'Abrió la encuesta de continuidad.' if aviso == 'apertura' else 'Todavía falta tu respuesta de continuidad.'
    encolar_email(clave=clave, tipo='continuidad', destinatario=usuario.email,
                  datos={'vigencia': {'usuario_id': usuario.pk, 'vencer_en': fin.isoformat(),
                                     'campana_fecha': fecha.isoformat(), 'encuestas': referencias},
                         'mensaje': {'parrafos': [texto], 'apartados': apartados}})
    return 1


def encolar_encuestas_continuidad():
    campana = campana_del_dia()
    if campana is None:
        return 0
    _, mes, aviso = campana
    ids = set()
    for modelo in MODELOS_CONTINUIDAD.values():
        contratos = modelo.objects.filter(mes_cubierto=mes).exclude(estado='anulado')
        if aviso != 'apertura':
            contratos = contratos.filter(respuesta_continuidad='')
        ids.update(contratos.values_list('usuario_id', flat=True))
    return sum(_encolar_para_titular(pk, campana) for pk in sorted(ids))
