from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from bloqueos.servicios import validar_anulacion_bloqueo
from common.fechas import FECHA_INICIO_OPERACIONES
from instalaciones.models import Cancha, Sede
from reservas.models import Evento
from reservas.servicios import validar_anulacion_reserva, validar_finalizacion_reserva


def enlace_agenda(sede, fecha, cancha=None, hora=None):
    datos = {"sede": sede.pk, "fecha": fecha.isoformat()}
    if cancha is not None:
        datos["cancha"] = cancha.pk
    if hora is not None:
        datos["hora"] = hora
    return reverse("agenda:agenda") + "?" + urlencode(datos)


def construir_agenda(sede, cancha, fecha, hora_seleccionada, fecha_maxima):
    ahora = timezone.localtime()
    canchas = list(sede.canchas.all())
    columnas = [{"cancha": cancha, "fecha": fecha} for cancha in canchas]

    horarios = {horario.dia_semana: horario for horario in sede.horarios.all()}
    inicios_habilitados = {}
    for dia in {columna["fecha"] for columna in columnas}:
        horario = horarios.get(dia.isoweekday())
        franjas = []
        if horario is not None:
            franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
            if horario.hora_inicio_2 is not None:
                franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
        inicios_habilitados[dia] = {
            hora for hora in range(23)
            if any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
        }

    fechas = [columna["fecha"] for columna in columnas]
    eventos = Evento.objects.none()
    if fechas:
        eventos = Evento.objects.filter(
            turno__cancha__in=[columna["cancha"] for columna in columnas],
            turno__fecha__range=(max(min(fechas), FECHA_INICIO_OPERACIONES), min(max(fechas), fecha_maxima)),
        ).exclude(estado=Evento.Estado.ANULADO).select_related(
            "turno__cancha__sede", "reserva__organizador", "registrado_por", "anulado_por",
            "bloqueo__origen__evento_origen__reserva",
        )
    eventos_por_turno = {
        (evento.turno.cancha_id, evento.turno.fecha, evento.turno.hora_inicio.hour): evento
        for evento in eventos
    }

    cancha_seleccionada = cancha

    def celda_para(cancha, dia, hora):
        inicio = timezone.make_aware(datetime.combine(dia, time(hora)))
        fin = inicio + timedelta(hours=1)
        evento = eventos_por_turno.get((cancha.pk, dia, hora))
        reserva = getattr(evento, "reserva", None) if evento and evento.tipo == Evento.Tipo.RESERVA else None
        bloqueo = getattr(evento, "bloqueo", None) if evento and evento.tipo == Evento.Tipo.BLOQUEO else None
        habilitado = hora in inicios_habilitados.get(dia, set())
        en_rango = FECHA_INICIO_OPERACIONES <= dia <= fecha_maxima
        impedimento = ""
        if not en_rango:
            impedimento = "La fecha está fuera del calendario operativo."
        elif inicio <= ahora:
            impedimento = "Este turno ya comenzó." if fin > ahora else "Este turno ya terminó."
        elif sede.estado != Sede.Estado.ACTIVA or cancha.estado != Cancha.Estado.ACTIVA:
            impedimento = "La sede y la cancha deben estar activas para registrar una reserva."
        elif not habilitado:
            impedimento = "Este turno está fuera del horario de funcionamiento de la sede."
        elif dia > ahora.date() + timedelta(days=14):
            impedimento = "Las reservas se registran con hasta catorce días de anticipación."
        elif sede.precio_reserva_vigente is None:
            impedimento = "La sede necesita un precio por turno configurado para registrar reservas."
        temporal = ""
        if evento:
            if evento.estado == Evento.Estado.FINALIZADO:
                temporal = "Finalizada"
            elif fin <= ahora:
                temporal = "Terminado" if bloqueo else "Terminada · pendiente de finalización"
            elif inicio <= ahora:
                temporal = "En curso"
            else:
                temporal = "Programada"
        puede_anular = False
        puede_finalizar = False
        puede_liberar_bloqueo = False
        if bloqueo:
            try:
                validar_anulacion_bloqueo(bloqueo, ahora)
            except ValidationError:
                pass
            else:
                puede_liberar_bloqueo = True
        if reserva:
            try:
                validar_anulacion_reserva(reserva, True, ahora)
            except ValidationError:
                pass
            else:
                puede_anular = True
            try:
                validar_finalizacion_reserva(reserva, ahora)
            except ValidationError:
                pass
            else:
                puede_finalizar = True
        return {
            "cancha": cancha, "fecha": dia, "hora": time(hora), "fin": fin.time(),
            "evento": evento, "reserva": reserva, "bloqueo": bloqueo,
            "habilitado": habilitado, "en_rango": en_rango,
            "consultable": evento is not None or fin > ahora,
            "iniciado": inicio <= ahora, "impedimento": impedimento, "estado_temporal": temporal,
            "puede_reservar": evento is None and not impedimento,
            "puede_anular": puede_anular, "puede_finalizar": puede_finalizar,
            "puede_bloquear": en_rango and habilitado and inicio > ahora
                and sede.estado == Sede.Estado.ACTIVA and cancha.estado == Cancha.Estado.ACTIVA
                and (evento is None or puede_anular),
            "puede_liberar_bloqueo": puede_liberar_bloqueo,
            "seleccionada": cancha.pk == (cancha_seleccionada.pk if cancha_seleccionada else None)
                and dia == fecha and hora == hora_seleccionada,
            "url": enlace_agenda(sede, dia, cancha, hora),
        }

    horas_visibles = set().union(*inicios_habilitados.values()) if inicios_habilitados else set()
    horas_visibles.update(clave[2] for clave in eventos_por_turno)
    filas = []
    if horas_visibles:
        for hora in range(min(horas_visibles), max(horas_visibles) + 1):
            if hora not in horas_visibles:
                if filas and filas[-1].get("pausa"):
                    filas[-1]["fin"] = time(hora + 1)
                else:
                    filas.append({"pausa": True, "inicio": time(hora), "fin": time(hora + 1)})
                continue
            filas.append({
                "hora": time(hora), "ahora": hora == ahora.hour and ahora.date() in fechas,
                "celdas": [celda_para(columna["cancha"], columna["fecha"], hora) for columna in columnas],
            })
    detalle = (
        celda_para(cancha, fecha, hora_seleccionada)
        if cancha is not None and hora_seleccionada is not None else None
    )
    if detalle and not detalle["consultable"]:
        detalle = None
    for columna in columnas:
        columna["hoy"] = columna["fecha"] == ahora.date()
    salto = timedelta(days=1)
    return {
        "columnas": columnas, "filas": filas, "detalle": detalle, "hoy": ahora.date(),
        "sede": sede, "cancha": cancha, "fecha": fecha,
        "url_anterior": enlace_agenda(sede, fecha - salto, cancha)
            if fecha - salto >= FECHA_INICIO_OPERACIONES else None,
        "url_siguiente": enlace_agenda(sede, fecha + salto, cancha)
            if fecha + salto <= fecha_maxima else None,
        "url_hoy": enlace_agenda(sede, ahora.date(), cancha),
        "url_cerrar": enlace_agenda(sede, fecha, cancha),
        "url_seleccion": enlace_agenda(sede, fecha, cancha, hora_seleccionada),
    }
