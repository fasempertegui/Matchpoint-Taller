from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import ExtractIsoWeekDay
from django.urls import reverse

from bloqueos.models import Bloqueo
from clases.consultas import clases_sin_asistencia_queryset
from clases.models import Asistencia, ClaseAlumno, ClaseProfesor
from reservas.models import Evento, ReservaInvitado

from .forms import EventosFiltroForm

TIPOS_EVENTO = ("todos", Evento.Tipo.CLASE, Evento.Tipo.RESERVA, Evento.Tipo.BLOQUEO)
RUTAS_PESTANAS = {
    "todos": "agenda:eventos_lista",
    Evento.Tipo.CLASE: "agenda:eventos_clases",
    Evento.Tipo.RESERVA: "agenda:eventos_reservas",
    Evento.Tipo.BLOQUEO: "agenda:eventos_bloqueos",
}
ETIQUETAS_TIPO = {
    Evento.Tipo.CLASE: "Clase",
    Evento.Tipo.RESERVA: "Reserva",
    Evento.Tipo.BLOQUEO: "Bloqueo",
}
CAMPOS_COMUNES = ("q", "estado", "desde", "hasta", "sede", "cancha", "dia_semana")
CAMPOS_ESPECIFICOS = {
    Evento.Tipo.CLASE: ("asistencia",),
    Evento.Tipo.RESERVA: ("modalidad", "resultado"),
}


def _condicion_busqueda_termino(termino, tipo):
    limpio = termino.lstrip("@") if termino.startswith("@") else termino
    texto_lower = termino.casefold()
    incluir_clases = tipo in ("todos", Evento.Tipo.CLASE)
    incluir_reservas = tipo in ("todos", Evento.Tipo.RESERVA)
    incluir_bloqueos = tipo in ("todos", Evento.Tipo.BLOQUEO)

    condicion = Q(pk__in=[])

    if texto_lower.startswith("r-") and texto_lower[2:].isdigit() and incluir_reservas:
        condicion |= Q(tipo=Evento.Tipo.RESERVA, reserva__pk=int(texto_lower[2:]))
    elif texto_lower.startswith("b-") and texto_lower[2:].isdigit() and incluir_bloqueos:
        condicion |= Q(tipo=Evento.Tipo.BLOQUEO, bloqueo__pk=int(texto_lower[2:]))
    elif termino.startswith("#") and termino[1:].isdigit() and incluir_clases:
        condicion |= Q(tipo=Evento.Tipo.CLASE, clase__pk=int(termino[1:]))
    elif termino.isdigit():
        numero = int(termino)
        if incluir_clases:
            condicion |= Q(tipo=Evento.Tipo.CLASE, clase__pk=numero)
        if incluir_reservas:
            condicion |= Q(tipo=Evento.Tipo.RESERVA, reserva__pk=numero)
        if incluir_bloqueos:
            condicion |= Q(tipo=Evento.Tipo.BLOQUEO, bloqueo__pk=numero)

    if limpio:
        if incluir_clases:
            if texto_lower == "clase":
                condicion |= Q(tipo=Evento.Tipo.CLASE)
            profesores = ClaseProfesor.objects.filter(
                clase__evento_id=OuterRef("pk"),
            ).filter(
                Q(profesor__first_name__icontains=limpio)
                | Q(profesor__last_name__icontains=limpio)
                | Q(profesor__username__icontains=limpio)
            )
            alumnos = ClaseAlumno.objects.filter(
                clase__evento_id=OuterRef("pk"),
            ).filter(
                Q(usuario__first_name__icontains=limpio)
                | Q(usuario__last_name__icontains=limpio)
                | Q(usuario__username__icontains=limpio)
            )
            condicion |= Q(tipo=Evento.Tipo.CLASE) & (Exists(profesores) | Exists(alumnos))

        if incluir_reservas:
            invitados = ReservaInvitado.objects.filter(
                reserva__evento_id=OuterRef("pk"),
            ).filter(
                Q(usuario__first_name__icontains=limpio)
                | Q(usuario__last_name__icontains=limpio)
                | Q(usuario__username__icontains=limpio)
            )
            condicion |= Q(tipo=Evento.Tipo.RESERVA) & (
                Q(reserva__organizador__first_name__icontains=limpio)
                | Q(reserva__organizador__last_name__icontains=limpio)
                | Q(reserva__organizador__username__icontains=limpio)
                | Exists(invitados)
            )

        if incluir_bloqueos:
            motivos = [
                valor for valor, etiqueta in Bloqueo.Motivo.choices
                if texto_lower in etiqueta.casefold()
            ]
            condicion_bloqueo = Q(observaciones__icontains=limpio)
            if motivos:
                condicion_bloqueo |= Q(bloqueo__motivo__in=motivos)
            condicion |= Q(tipo=Evento.Tipo.BLOQUEO) & condicion_bloqueo

    return condicion


def _resumir_texto(texto, maximo=80):
    limpio = " ".join((texto or "").split())
    if len(limpio) <= maximo:
        return limpio
    return limpio[: maximo - 1].rstrip() + "…"


def _fila_evento(evento):
    turno = evento.turno
    base = {
        "evento": evento,
        "tipo": evento.tipo,
        "tipo_texto": ETIQUETAS_TIPO[evento.tipo],
        "fecha": turno.fecha,
        "hora_inicio": turno.hora_inicio,
        "hora_fin": turno.hora_fin,
        "sede_nombre": turno.cancha.sede.nombre,
        "cancha_nombre": turno.cancha.nombre,
        "estado": evento.estado,
        "detalle_principal": "",
        "detalle_principal_secundario": "",
        "detalle_principal_suave": False,
        "detalle_secundario": "",
        "detalle_aviso": "",
    }

    if evento.tipo == Evento.Tipo.CLASE:
        clase = evento.clase
        profesores = sorted((str(item.profesor) for item in clase.profesores.all()), key=str.casefold)
        cantidad_alumnos = len(clase.alumnos.all())
        pendientes = 0
        if evento.estado == Evento.Estado.FINALIZADO:
            registradas = {
                a.usuario_id for a in clase.asistencias.all()
                if a.estado in (Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE)
            }
            pendientes = len(
                {al.usuario_id for al in clase.alumnos.all() if al.usuario_id not in registradas}
                | {a.usuario_id for a in clase.asistencias.all() if a.estado == Asistencia.Estado.SIN_REGISTRAR}
            )
        secundario = (
            f"{cantidad_alumnos} participante{'s' if cantidad_alumnos != 1 else ''}"
            if cantidad_alumnos else "Sin participantes"
        )
        base.update({
            "codigo": f"Clase #{clase.pk}",
            "url_detalle": reverse("clases:clase_detalle", args=[clase.pk]),
            "detalle_principal": ", ".join(profesores) if profesores else "Sin profesores asignados",
            "detalle_principal_suave": not profesores,
            "detalle_secundario": secundario,
            "detalle_aviso": f"{pendientes} sin asistencia" if pendientes else "",
        })
    elif evento.tipo == Evento.Tipo.RESERVA:
        reserva = evento.reserva
        modalidad = (
            reserva.membresia_usuario.membresia.nombre
            if reserva.es_con_membresia else "Normal"
        )
        aviso = ""
        if reserva.es_con_membresia:
            if evento.estado == Evento.Estado.FINALIZADO and reserva.resultado_uso == "sin_registrar":
                aviso = "Sin resultado"
            elif reserva.resultado_uso in ("realizada", "no_realizada"):
                modalidad = f"{modalidad} · {reserva.get_resultado_uso_display()}"
        base.update({
            "codigo": reserva.numero,
            "url_detalle": reverse("reservas:reserva_detalle", args=[reserva.pk]),
            "detalle_principal": str(reserva.organizador),
            "detalle_principal_secundario": f"@{reserva.organizador.username}",
            "detalle_secundario": modalidad,
            "detalle_aviso": aviso,
        })
    else:
        bloqueo = evento.bloqueo
        secundario = "Por anulación" if bloqueo.evento_origen_id else _resumir_texto(evento.observaciones)
        base.update({
            "codigo": bloqueo.numero,
            "url_detalle": reverse("agenda:bloqueo_detalle", args=[bloqueo.pk]),
            "detalle_principal": bloqueo.get_motivo_display(),
            "detalle_secundario": secundario,
        })

    return base


def _serializar_parametros(datos, campos):
    pares = {}
    for campo in campos:
        valor = datos.get(campo)
        if valor in (None, ""):
            continue
        if hasattr(valor, "pk"):
            pares[campo] = str(valor.pk)
        elif hasattr(valor, "isoformat"):
            pares[campo] = valor.isoformat()
        else:
            pares[campo] = str(valor)
    return urlencode(pares)


def listar_eventos_administracion(parametros, *, tipo="todos"):
    if tipo not in TIPOS_EVENTO:
        tipo = "todos"

    base = Evento.objects.filter(
        tipo__in=(Evento.Tipo.CLASE, Evento.Tipo.RESERVA, Evento.Tipo.BLOQUEO),
    )
    if tipo != "todos":
        base = base.filter(tipo=tipo)
    hay_eventos = base.exists()

    formulario = EventosFiltroForm(parametros, tipo=tipo)
    formulario_valido = formulario.is_valid()
    filtros = formulario.cleaned_data if formulario_valido else {}

    if formulario_valido and hay_eventos:
        consulta = base
        busqueda = filtros.get("q", "").strip()
        if busqueda:
            for termino in busqueda.split():
                consulta = consulta.filter(_condicion_busqueda_termino(termino, tipo))
        if filtros.get("estado"):
            consulta = consulta.filter(estado=filtros["estado"])
        if filtros.get("desde"):
            consulta = consulta.filter(turno__fecha__gte=filtros["desde"])
        if filtros.get("hasta"):
            consulta = consulta.filter(turno__fecha__lte=filtros["hasta"])
        if filtros.get("sede"):
            consulta = consulta.filter(turno__cancha__sede=filtros["sede"])
        if filtros.get("cancha"):
            consulta = consulta.filter(turno__cancha=filtros["cancha"])
        if filtros.get("dia_semana"):
            consulta = consulta.annotate(
                dia_semana_iso=ExtractIsoWeekDay("turno__fecha"),
            ).filter(dia_semana_iso=filtros["dia_semana"])

        if tipo == Evento.Tipo.CLASE:
            asistencia = filtros.get("asistencia", "")
            if asistencia == "pendiente":
                consulta = consulta.filter(
                    estado=Evento.Estado.FINALIZADO,
                    clase__in=clases_sin_asistencia_queryset(),
                )
            elif asistencia == "completa":
                consulta = consulta.filter(
                    estado=Evento.Estado.FINALIZADO,
                ).exclude(clase__in=clases_sin_asistencia_queryset())
        elif tipo == Evento.Tipo.RESERVA:
            modalidad = filtros.get("modalidad", "")
            if modalidad == "normal":
                consulta = consulta.filter(reserva__membresia_usuario__isnull=True)
            elif modalidad == "membresia":
                consulta = consulta.filter(reserva__membresia_usuario__isnull=False)
            resultado = filtros.get("resultado", "")
            if modalidad != "normal" and resultado:
                consulta = consulta.filter(
                    reserva__membresia_usuario__isnull=False,
                    reserva__resultado_uso=resultado,
                )

        consulta = consulta.select_related(
            "turno__cancha__sede",
            "clase",
            "reserva__organizador",
            "reserva__membresia_usuario__membresia",
            "bloqueo",
        ).prefetch_related(
            "clase__profesores__profesor",
            "clase__alumnos",
            "clase__asistencias",
        ).order_by("-turno__fecha", "-turno__hora_inicio", "-pk")

        pagina = Paginator(consulta, 25).get_page(parametros.get("pagina"))
        filas = [_fila_evento(evento) for evento in pagina]
    else:
        pagina = None
        filas = []

    if formulario_valido:
        consulta_comunes = _serializar_parametros(filtros, CAMPOS_COMUNES)
        consulta_pagina = _serializar_parametros(
            filtros, CAMPOS_COMUNES + CAMPOS_ESPECIFICOS.get(tipo, ()),
        )
    else:
        consulta_comunes = urlencode({
            clave: parametros.get(clave, "").strip()
            for clave in CAMPOS_COMUNES
            if parametros.get(clave, "").strip()
        })
        consulta_pagina = ""

    sufijo_comunes = f"?{consulta_comunes}" if consulta_comunes else ""
    url_limpiar = reverse(RUTAS_PESTANAS[tipo])
    hay_parametros = any(
        valor for clave, valores in parametros.lists() if clave != "pagina" for valor in valores
    )

    return {
        "tipo": tipo,
        "hay_eventos": hay_eventos,
        "formulario": formulario,
        "formulario_valido": formulario_valido,
        "filtros_abiertos": hay_parametros or bool(formulario.errors),
        "pagina": pagina,
        "filas": filas,
        "parametros": consulta_pagina,
        "url_limpiar": url_limpiar,
        "url_tab_todos": f"{reverse('agenda:eventos_lista')}{sufijo_comunes}",
        "url_tab_clases": f"{reverse('agenda:eventos_clases')}{sufijo_comunes}",
        "url_tab_reservas": f"{reverse('agenda:eventos_reservas')}{sufijo_comunes}",
        "url_tab_bloqueos": f"{reverse('agenda:eventos_bloqueos')}{sufijo_comunes}",
    }
