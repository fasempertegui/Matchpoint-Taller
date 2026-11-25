from datetime import date
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from clases.consultas import _clases_de_actividad, _fila_actividad_clase, resumen_clases_mes
from clases.models import Asistencia, ClaseAlumno
from common.fechas import FECHA_INICIO_OPERACIONES, opciones_meses_agenda
from reservas.models import Evento, Reserva, ReservaInvitado
from usuarios.acceso import exigir_acceso_operativo
from usuarios.models import Rol


class MiActividadMensualForm(forms.Form):
    mes = forms.ChoiceField(
        label="Mes",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes"].choices = list(reversed(opciones_meses_agenda(desde=FECHA_INICIO_OPERACIONES)))


def exigir_titular_actividad_mensual(usuario):
    titular = exigir_acceso_operativo(usuario)
    if titular.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    return titular


def consultar_mi_actividad_mensual(titular, mes_codigo, numero_pagina=None):
    mes_fecha = date.fromisoformat(f"{mes_codigo}-01")
    es_profesor = titular.tiene_rol(Rol.PROFESOR)
    es_alumno = titular.tiene_rol(Rol.ALUMNO)
    puede_reservar = titular.puede_reservar

    resumen_clases = resumen_clases_mes(titular, mes_fecha)

    clases = (
        _clases_de_actividad(titular.pk)
        .filter(
            Q(tiene_docencia=True) | Q(tiene_participacion=True) | Q(tiene_asistencia=True),
            evento__turno__fecha__year=mes_fecha.year,
            evento__turno__fecha__month=mes_fecha.month,
        )
        .order_by("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
    )

    filas = []
    for clase in clases:
        fila_clase = _fila_actividad_clase(clase)
        url_clase = reverse("clases:clase_detalle", args=[clase.pk])
        if fila_clase["asignacion_profesor"]:
            filas.append({
                "fecha": fila_clase["fecha"],
                "hora_inicio": fila_clase["hora_inicio"],
                "hora_fin": fila_clase["hora_fin"],
                "tipo": "Clase",
                "tipo_codigo": "clase",
                "referencia": "",
                "sede": fila_clase["sede"]["nombre"],
                "cancha": fila_clase["cancha"]["nombre"],
                "funcion": "Profesor",
                "funcion_clase": "profesor",
                "estado": fila_clase["estado"],
                "estado_texto": fila_clase["estado_texto"],
                "asistencia": None,
                "asistencia_texto": None,
                "aviso_previo": None,
                "sin_asignacion": False,
                "resultado_uso": None,
                "condicion_invitado": None,
                "url": url_clase,
                "accion_texto": "Ver clase",
                "orden_id": clase.pk,
            })
        if fila_clase["asignacion_participante"] or fila_clase["asistencia"] is not None:
            asistencia_estado = (
                fila_clase["asistencia"]
                if fila_clase["estado"] == Evento.Estado.FINALIZADO and fila_clase["asistencia"] is not None
                else None
            )
            aviso_previo = (
                "Avisó no asistencia"
                if fila_clase["respuesta"] == ClaseAlumno.Respuesta.NO_ASISTIRA
                else None
            )
            filas.append({
                "fecha": fila_clase["fecha"],
                "hora_inicio": fila_clase["hora_inicio"],
                "hora_fin": fila_clase["hora_fin"],
                "tipo": "Clase",
                "tipo_codigo": "clase",
                "referencia": "",
                "sede": fila_clase["sede"]["nombre"],
                "cancha": fila_clase["cancha"]["nombre"],
                "funcion": "Participante",
                "funcion_clase": "alumno",
                "estado": fila_clase["estado"],
                "estado_texto": fila_clase["estado_texto"],
                "asistencia": asistencia_estado,
                "asistencia_texto": fila_clase["asistencia_texto"],
                "aviso_previo": aviso_previo,
                "sin_asignacion": not fila_clase["asignacion_participante"] and fila_clase["asistencia"] is not None,
                "resultado_uso": None,
                "condicion_invitado": None,
                "url": url_clase,
                "accion_texto": "Ver clase",
                "orden_id": clase.pk,
            })

    reservas_qs = (
        Reserva.objects.filter(
            Q(organizador=titular)
            | Q(invitados__usuario=titular, invitados__respuesta=ReservaInvitado.Respuesta.AFIRMATIVA),
            evento__turno__fecha__year=mes_fecha.year,
            evento__turno__fecha__month=mes_fecha.month,
        )
        .select_related("evento__turno__cancha__sede")
        .prefetch_related(
            Prefetch(
                "invitados",
                queryset=ReservaInvitado.objects.filter(usuario=titular),
                to_attr="invitaciones_del_titular",
            ),
        )
        .distinct()
        .order_by("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
    )

    organizadas = 0
    invitaciones_aceptadas = 0
    for reserva in reservas_qs:
        turno = reserva.evento.turno
        es_organizador = reserva.organizador_id == titular.pk
        if reserva.evento.estado != Evento.Estado.ANULADO:
            if es_organizador:
                organizadas += 1
            else:
                invitaciones_aceptadas += 1

        resultado_uso = None
        condicion_invitado = None
        if es_organizador:
            if (
                reserva.es_con_membresia
                and reserva.evento.estado == Evento.Estado.FINALIZADO
                and reserva.resultado_uso != "sin_registrar"
            ):
                resultado_uso = reserva.get_resultado_uso_display()
        else:
            invitacion = next(iter(reserva.invitaciones_del_titular), None)
            if invitacion is not None and invitacion.participacion_computable:
                condicion_invitado = invitacion.get_condicion_aplicada_display()

        filas.append({
            "fecha": turno.fecha,
            "hora_inicio": turno.hora_inicio,
            "hora_fin": turno.hora_fin,
            "tipo": "Reserva",
            "tipo_codigo": "reserva",
            "referencia": reserva.numero,
            "sede": turno.cancha.sede.nombre,
            "cancha": turno.cancha.nombre,
            "funcion": "Organizador" if es_organizador else "Invitado",
            "funcion_clase": "reserva",
            "estado": reserva.evento.estado,
            "estado_texto": reserva.evento.get_estado_display(),
            "asistencia": None,
            "asistencia_texto": None,
            "aviso_previo": None,
            "sin_asignacion": False,
            "resultado_uso": resultado_uso,
            "condicion_invitado": condicion_invitado,
            "url": reverse("reservas:reserva_detalle", args=[reserva.pk]) if puede_reservar else None,
            "accion_texto": "Detalles",
            "orden_id": reserva.pk,
        })

    filas.sort(
        key=lambda item: (item["fecha"], item["hora_inicio"], item["tipo_codigo"], item["orden_id"]),
        reverse=True,
    )

    reservas_resumen = {
        "organizadas": organizadas,
        "invitaciones": invitaciones_aceptadas,
        "total": organizadas + invitaciones_aceptadas,
    }
    pagina = Paginator(filas, 20).get_page(numero_pagina)

    return {
        "mes_fecha": mes_fecha,
        "participante": resumen_clases["participante"],
        "profesor": resumen_clases["profesor"],
        "reservas": reservas_resumen,
        "mostrar_participante": es_alumno or resumen_clases["participante"]["tiene_actividad"],
        "mostrar_profesor": es_profesor or resumen_clases["profesor"]["tiene_actividad"],
        "mostrar_reservas": puede_reservar or reservas_resumen["total"] > 0,
        "total_eventos_mes": len(filas),
        "pagina": pagina,
        "parametros": urlencode({"mes": mes_codigo}),
    }


def contexto_mi_actividad_mensual(request):
    titular = exigir_titular_actividad_mensual(request.user)
    hoy = timezone.localdate()
    mes_actual = max(hoy, FECHA_INICIO_OPERACIONES).strftime("%Y-%m")
    parametros = request.GET.copy()
    parametros.setdefault("mes", mes_actual)
    formulario = MiActividadMensualForm(parametros)
    datos = None
    mes_etiqueta = ""
    if formulario.is_valid():
        mes_codigo = formulario.cleaned_data["mes"]
        mes_etiqueta = dict(formulario.fields["mes"].choices).get(mes_codigo, mes_codigo)
        datos = consultar_mi_actividad_mensual(titular, mes_codigo, request.GET.get("pagina"))
    return {
        "formulario": formulario,
        "datos": datos,
        "mes_etiqueta": mes_etiqueta,
        "mes_actual": mes_actual,
    }
