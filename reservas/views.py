from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from agenda.servicios import enlace_agenda

from .forms import ReservaAnulacionForm
from .models import Reserva
from .servicios import (
    anular_reserva,
    exigir_acceso_reservas,
    finalizar_reserva,
    validar_anulacion_reserva,
    validar_finalizacion_reserva,
)


def _breadcrumbs_reserva(reserva):
    turno = reserva.evento.turno
    return [
        ("Inicio", reverse("inicio")),
        ("Agenda", enlace_agenda(turno.cancha.sede, turno.fecha, turno.cancha, turno.hora_inicio.hour)),
        (reserva.numero, reverse("reservas:reserva_detalle", args=[reserva.pk])),
    ]


@login_required
@require_http_methods(["GET"])
def reserva_detalle(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    return render(request, "reservas/reserva_detalle.html", _contexto_reserva_detalle(reserva, es_administrador))


@login_required
@require_http_methods(["GET"])
def reserva_comprobante(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    return render(request, "reservas/reserva_comprobante.html", {
        "reserva": reserva,
        "turno": reserva.evento.turno,
        "total": reserva.precio_por_turno_aplicado,
        "breadcrumbs": _breadcrumbs_reserva(reserva) + [("Comprobante", None)],
    })


def _obtener_reserva_para_consulta(usuario, pk):
    es_administrador = exigir_acceso_reservas(usuario)
    reservas = Reserva.objects.select_related(
        "organizador", "evento__registrado_por", "evento__anulado_por", "evento__turno__cancha__sede",
    )
    if not es_administrador:
        reservas = reservas.filter(organizador=usuario)
    return get_object_or_404(reservas, pk=pk), es_administrador


def _contexto_reserva_detalle(reserva, es_administrador, formulario_anulacion=None):
    ahora = timezone.localtime()
    try:
        validar_anulacion_reserva(reserva, es_administrador, ahora)
    except ValidationError as error:
        puede_anular = False
        impedimento_anulacion = error.messages[0]
    else:
        puede_anular = True
        impedimento_anulacion = ""
    puede_finalizar = False
    if es_administrador:
        try:
            validar_finalizacion_reserva(reserva, ahora)
        except ValidationError:
            pass
        else:
            puede_finalizar = True
    return {
        "reserva": reserva,
        "turno": reserva.evento.turno,
        "total": reserva.precio_por_turno_aplicado,
        "puede_anular": puede_anular,
        "puede_finalizar": puede_finalizar,
        "es_administrador": es_administrador,
        "impedimento_anulacion": impedimento_anulacion,
        "breadcrumbs": _breadcrumbs_reserva(reserva),
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
            messages.success(request, f"La reserva {reserva.numero} fue anulada. Su turno quedó liberado.")
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
