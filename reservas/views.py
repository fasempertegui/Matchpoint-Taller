from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.formats import number_format
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .disponibilidad import consultar_disponibilidad
from .forms import ReservaAnulacionForm, ReservaDatosForm, ReservaFiltroForm, ReservaTurnosForm
from .models import Reserva, Turno
from .servicios import (
    anular_reserva,
    exigir_acceso_reservas,
    finalizar_reserva,
    registrar_reserva,
    validar_anulacion_reserva,
    validar_finalizacion_reserva,
)


def _breadcrumbs_reserva(es_administrador, reserva=None):
    breadcrumbs = [
        ("Inicio", reverse("inicio")),
        ("Reservas" if es_administrador else "Mis reservas", reverse("reservas:reserva_lista")),
    ]
    if reserva is not None:
        breadcrumbs.append((reserva.numero, reverse("reservas:reserva_detalle", args=[reserva.pk])))
    return breadcrumbs


@login_required
@require_http_methods(["GET"])
def reserva_lista(request):
    es_administrador = exigir_acceso_reservas(request.user)
    formulario = ReservaFiltroForm(request.GET, es_administrador=es_administrador)
    reservas = Reserva.objects.select_related("organizador", "evento").prefetch_related(
        Prefetch("evento__turnos", queryset=Turno.objects.select_related("cancha__sede"))
    )
    if not es_administrador:
        reservas = reservas.filter(organizador=request.user)
    filtros_validos = formulario.is_valid()
    if filtros_validos:
        datos = formulario.cleaned_data
        filtros_turnos = {}
        if datos["sede"]:
            filtros_turnos["evento__turnos__cancha__sede"] = datos["sede"]
        if datos["cancha"]:
            filtros_turnos["evento__turnos__cancha"] = datos["cancha"]
        if datos["fecha_desde"]:
            filtros_turnos["evento__turnos__fecha__gte"] = datos["fecha_desde"]
        if datos["fecha_hasta"]:
            filtros_turnos["evento__turnos__fecha__lte"] = datos["fecha_hasta"]
        if filtros_turnos:
            reservas = reservas.filter(**filtros_turnos).distinct()
        if datos["estado"]:
            reservas = reservas.filter(evento__estado=datos["estado"])
        if datos["numero"] is not None:
            reservas = reservas.filter(pk=datos["numero"])
        for palabra in datos.get("organizador", "").split():
            reservas = reservas.filter(
                Q(organizador__first_name__icontains=palabra)
                | Q(organizador__last_name__icontains=palabra)
            )
    else:
        reservas = reservas.none()

    filas = []
    for reserva in reservas:
        turnos = list(reserva.evento.turnos.all())
        primer_turno = turnos[0]
        ultimo_turno = turnos[-1]
        filas.append({
            "reserva": reserva,
            "cancha": primer_turno.cancha,
            "fecha": primer_turno.fecha,
            "hora_inicio": primer_turno.hora_inicio,
            "hora_fin": ultimo_turno.hora_fin,
            "total": reserva.precio_por_turno_aplicado * len(turnos),
        })
    return render(request, "reservas/reserva_lista.html", {
        "formulario": formulario,
        "reservas": filas,
        "es_administrador": es_administrador,
        "filtros_validos": filtros_validos,
        "breadcrumbs": _breadcrumbs_reserva(es_administrador),
    })


@login_required
@require_http_methods(["GET", "POST"])
def reserva_crear(request):
    es_administrador = exigir_acceso_reservas(request.user)
    formulario = ReservaDatosForm(
        request.POST if request.method == "POST" else None,
        es_administrador=es_administrador,
    )
    resultado = None
    formulario_turnos = None
    if request.method == "POST" and formulario.is_valid():
        accion = request.POST.get("accion")
        try:
            if accion not in ("consultar", "registrar"):
                raise ValidationError("La acción solicitada no es válida.")
            resultado = consultar_disponibilidad(
                formulario.cleaned_data["cancha"],
                formulario.cleaned_data["fecha"],
            )
            formulario_turnos = ReservaTurnosForm(
                request.POST if accion == "registrar" else None,
                turnos=resultado["turnos"],
            )
            if accion == "registrar" and formulario_turnos.is_valid():
                try:
                    reserva, total = registrar_reserva(
                        request.user,
                        formulario.cleaned_data.get("organizador", request.user),
                        formulario.cleaned_data["cancha"],
                        formulario.cleaned_data["fecha"],
                        formulario_turnos.cleaned_data["turnos"],
                        formulario_turnos.cleaned_data["precio_mostrado"],
                        formulario_turnos.cleaned_data["observaciones"],
                    )
                except ValidationError as error:
                    resultado = consultar_disponibilidad(
                        formulario.cleaned_data["cancha"],
                        formulario.cleaned_data["fecha"],
                    )
                    formulario_turnos = ReservaTurnosForm(request.POST, turnos=resultado["turnos"])
                    formulario_turnos.add_error(None, error)
                else:
                    messages.success(request, f"La reserva {reserva.numero} fue registrada. Total: $ {number_format(total, decimal_pos=2)}.")
                    return redirect("reservas:reserva_detalle", pk=reserva.pk)
        except ValidationError as error:
            formulario.add_error(None, error)
            resultado = None
            formulario_turnos = None

    filas_turnos = []
    if resultado is not None:
        filas_turnos = [
            {
                "turno": turno,
                "franja": next(
                    numero for numero, (inicio, fin) in enumerate(resultado["franjas"])
                    if turno.hora_inicio >= inicio and turno.hora_fin <= fin
                ),
            }
            for turno in resultado["turnos"]
        ]
    return render(request, "reservas/reserva_formulario.html", {
        "formulario": formulario,
        "formulario_turnos": formulario_turnos,
        "resultado": resultado,
        "filas_turnos": filas_turnos,
        "turnos_seleccionados": request.POST.getlist("turnos"),
        "precio_centavos": int(resultado["precio_por_turno"] * 100) if resultado else None,
        "es_administrador": es_administrador,
        "hay_sedes": formulario.fields["sede"].queryset.exists(),
        "breadcrumbs": _breadcrumbs_reserva(es_administrador) + [("Nueva reserva", None)],
    })


@login_required
@require_http_methods(["GET"])
def reserva_detalle(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    return render(request, "reservas/reserva_detalle.html", _contexto_reserva_detalle(reserva, es_administrador))


@login_required
@require_http_methods(["GET"])
def reserva_comprobante(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    turnos = list(reserva.evento.turnos.select_related("cancha__sede").all())
    return render(request, "reservas/reserva_comprobante.html", {
        "reserva": reserva,
        "turnos": turnos,
        "cantidad_horas": len(turnos),
        "total": reserva.precio_por_turno_aplicado * len(turnos),
        "hora_inicio": turnos[0].hora_inicio if turnos else None,
        "hora_fin": turnos[-1].hora_fin if turnos else None,
        "breadcrumbs": _breadcrumbs_reserva(es_administrador, reserva) + [("Comprobante", None)],
    })


def _obtener_reserva_para_consulta(usuario, pk):
    es_administrador = exigir_acceso_reservas(usuario)
    reservas = Reserva.objects.select_related(
        "organizador", "evento__registrado_por", "evento__anulado_por",
    )
    if not es_administrador:
        reservas = reservas.filter(organizador=usuario)
    return get_object_or_404(reservas, pk=pk), es_administrador


def _contexto_reserva_detalle(reserva, es_administrador, formulario_anulacion=None):
    turnos = list(reserva.evento.turnos.select_related("cancha__sede").all())
    ahora = timezone.localtime()
    primer_turno = turnos[0] if turnos else None
    ultimo_turno = turnos[-1] if turnos else None
    try:
        validar_anulacion_reserva(reserva, primer_turno, es_administrador, ahora)
    except ValidationError as error:
        puede_anular = False
        impedimento_anulacion = error.messages[0]
    else:
        puede_anular = True
        impedimento_anulacion = ""
    puede_finalizar = False
    if es_administrador:
        try:
            validar_finalizacion_reserva(reserva, ultimo_turno, ahora)
        except ValidationError:
            pass
        else:
            puede_finalizar = True
    return {
        "reserva": reserva,
        "turnos": turnos,
        "cantidad_horas": len(turnos),
        "total": reserva.precio_por_turno_aplicado * len(turnos),
        "puede_anular": puede_anular,
        "puede_finalizar": puede_finalizar,
        "hora_inicio": primer_turno.hora_inicio if primer_turno else None,
        "hora_fin": ultimo_turno.hora_fin if ultimo_turno else None,
        "es_administrador": es_administrador,
        "impedimento_anulacion": impedimento_anulacion,
        "breadcrumbs": _breadcrumbs_reserva(es_administrador, reserva),
        "formulario_anulacion": formulario_anulacion if formulario_anulacion is not None else ReservaAnulacionForm(),
    }


@login_required
@require_http_methods(["POST"])
def reserva_anular(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    formulario = ReservaAnulacionForm(request.POST)
    if formulario.is_valid():
        try:
            reserva = anular_reserva(request.user, reserva.pk, formulario.cleaned_data["motivo"])
        except ValidationError as error:
            formulario.add_error(None, error)
            reserva.refresh_from_db()
        else:
            messages.success(request, f"La reserva {reserva.numero} fue anulada. Sus turnos quedaron liberados.")
            return redirect("reservas:reserva_detalle", pk=reserva.pk)
    return render(request, "reservas/reserva_detalle.html", _contexto_reserva_detalle(reserva, es_administrador, formulario))


@login_required
@require_http_methods(["POST"])
def reserva_finalizar(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    if not es_administrador:
        raise PermissionDenied
    try:
        reserva = finalizar_reserva(reserva.pk, usuario=request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"La reserva {reserva.numero} fue finalizada.")
    return redirect("reservas:reserva_detalle", pk=reserva.pk)
