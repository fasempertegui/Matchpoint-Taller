from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from caja.consultas import contexto_financiero
from common.modales import es_peticion_modal, respuesta_modal_exito, respuesta_modal_html
from instalaciones.models import Sede

from .forms import ReservaAnulacionForm
from .models import Evento, Reserva
from .servicios import (
    anular_reserva,
    exigir_acceso_reservas,
    finalizar_reserva,
    reservas_sin_resultado_queryset,
    validar_anulacion_reserva,
    validar_finalizacion_reserva,
)


@login_required
@require_http_methods(["GET"])
def reserva_detalle(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    from .comercial import inicio_reserva, version_invitacion
    if not es_administrador and reserva.organizador_id != request.user.pk:
        request.detalle_invitacion = True
        invitacion = reserva.invitados.get(usuario=request.user)
        return render(request, "reservas/reserva_invitacion.html", {
            "reserva": reserva, "invitacion": invitacion, "respuesta_texto": invitacion.get_respuesta_display(),
            "version": version_invitacion(request.user, invitacion),
            "puede_responder": reserva.evento.estado == Evento.Estado.PROGRAMADO and timezone.now() < inicio_reserva(reserva),
        })
    return render(request, "reservas/reserva_detalle.html", _contexto_reserva_detalle(reserva, es_administrador, usuario=request.user, parametros=request.GET))


@login_required
@require_http_methods(["GET"])
def reserva_comprobante(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk, solo_organizador=True)
    return render(request, "reservas/reserva_comprobante.html", {
        "reserva": reserva,
        "turno": reserva.evento.turno,
        "total": reserva.importe_acordado,
    })


def _obtener_reserva_para_consulta(usuario, pk, *, solo_organizador=False):
    es_administrador = exigir_acceso_reservas(usuario)
    reservas = Reserva.objects.select_related(
        "organizador", "evento__registrado_por", "evento__anulado_por", "evento__turno__cancha__sede",
    )
    if not es_administrador:
        reservas = reservas.filter(organizador=usuario) if solo_organizador else reservas.filter(Q(organizador=usuario) | Q(invitados__usuario=usuario)).distinct()
    return get_object_or_404(reservas, pk=pk), es_administrador


def _contexto_reserva_detalle(reserva, es_administrador, *, usuario, parametros):
    from .comercial import inicio_reserva, version_invitacion
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
    mi_invitacion = reserva.invitados.filter(usuario=usuario).first()
    return {
        "mi_invitacion": mi_invitacion,
        "version": version_invitacion(usuario, mi_invitacion) if mi_invitacion else None,
        "respuesta_texto": mi_invitacion.get_respuesta_display() if mi_invitacion else None,
        "puede_responder": mi_invitacion is not None and reserva.evento.estado == Evento.Estado.PROGRAMADO and ahora < inicio_reserva(reserva),
        **contexto_financiero(usuario, "reserva", reserva, parametros),
        "reserva": reserva,
        "turno": reserva.evento.turno,
        "total": reserva.importe_acordado,
        "invitados": [{"invitado": i, "respuesta_texto": i.get_respuesta_display()} for i in reserva.invitados.select_related("usuario").order_by("usuario__last_name", "usuario__first_name")],
        "puede_gestionar": reserva.evento.estado == Evento.Estado.PROGRAMADO and ahora < inicio_reserva(reserva),
        "puede_anular": puede_anular,
        "puede_finalizar": puede_finalizar,
        "es_administrador": es_administrador,
        "impedimento_anulacion": impedimento_anulacion,
    }


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def reserva_anular(request, pk):
    reserva, es_administrador = _obtener_reserva_para_consulta(request.user, pk)
    if not es_administrador and reserva.organizador_id != request.user.pk:
        raise PermissionDenied
    url_detalle = reverse("reservas:reserva_detalle", args=[reserva.pk])
    if not es_peticion_modal(request):
        return redirect(url_detalle)

    destino = request.POST.get("siguiente") or request.GET.get("siguiente") or url_detalle
    if not destino.startswith("/") or destino.startswith("//"):
        destino = url_detalle

    try:
        validar_anulacion_reserva(reserva, es_administrador, timezone.localtime())
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return respuesta_modal_exito(destino)

    formulario = ReservaAnulacionForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and formulario.is_valid():
        try:
            reserva = anular_reserva(request.user, reserva.pk, formulario.cleaned_data["motivo"])
        except ValidationError as error:
            formulario.add_error(None, error)
            reserva.refresh_from_db()
        else:
            messages.success(request, f"La reserva {reserva.numero} fue anulada. El turno y el cupo Programado quedaron liberados.")
            return respuesta_modal_exito(destino)

    return respuesta_modal_html(
        request,
        "reservas/_modal_reserva_anular.html",
        {
            "reserva": reserva,
            "turno": reserva.evento.turno,
            "es_administrador": es_administrador,
            "formulario": formulario,
            "siguiente": destino if destino != url_detalle else "",
        },
        status=400 if formulario.errors else 200,
        peligro=True,
        amplio=True,
        errores=bool(formulario.errors),
    )


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


@login_required
@never_cache
@require_GET
def reservas_sin_resultado(request):
    if not exigir_acceso_reservas(request.user):
        raise PermissionDenied
    base = reservas_sin_resultado_queryset()
    hay_pendientes = base.exists()
    sedes = list(Sede.objects.order_by("nombre"))
    sede_actual = request.GET.get("sede", "")
    if sede_actual not in {str(sede.pk) for sede in sedes}:
        sede_actual = ""
    busqueda = request.GET.get("q", "").strip()[:150]

    reservas = base
    if sede_actual:
        reservas = reservas.filter(evento__turno__cancha__sede_id=sede_actual)
    if busqueda:
        for termino in busqueda.split():
            reservas = reservas.filter(
                Q(organizador__first_name__icontains=termino)
                | Q(organizador__last_name__icontains=termino)
                | Q(organizador__username__icontains=termino)
            )
    reservas = reservas.select_related(
        "organizador", "membresia_usuario__membresia", "evento__turno__cancha__sede",
    ).order_by("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
    pagina = Paginator(reservas, 25).get_page(request.GET.get("pagina"))
    parametros = urlencode({
        clave: valor
        for clave, valor in (("q", busqueda), ("sede", sede_actual))
        if valor
    })
    return render(request, "reservas/reservas_sin_resultado.html", {
        "pagina": pagina,
        "hay_pendientes": hay_pendientes,
        "sedes": sedes,
        "sede_actual": sede_actual,
        "busqueda": busqueda,
        "parametros": parametros,
    })
