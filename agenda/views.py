from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_headers

from instalaciones.models import Sede
from reservas.disponibilidad import consultar_disponibilidad
from reservas.forms import ReservaAnulacionForm
from reservas.servicios import anular_reserva, exigir_acceso_reservas, finalizar_reserva, registrar_reserva

from .forms import AgendaFiltroForm, AgendaReservaForm
from .servicios import construir_agenda


@login_required
@never_cache
@vary_on_headers("X-Agenda-Detalle")
@require_http_methods(["GET", "POST"])
def agenda(request):
    if not exigir_acceso_reservas(request.user):
        raise PermissionDenied

    parametros = request.GET.copy()
    parametros.setdefault("fecha", timezone.localdate().isoformat())
    sede_inicial = Sede.objects.order_by("estado", "nombre").first()
    if sede_inicial is not None:
        parametros.setdefault("sede", str(sede_inicial.pk))
    formulario = AgendaFiltroForm(parametros)
    accion = request.POST.get("accion") if request.method == "POST" else None
    formulario_reserva = AgendaReservaForm(request.POST if accion == "reservar" else None)
    formulario_anulacion = ReservaAnulacionForm(request.POST if accion == "anular" else None)
    datos = {}
    if sede_inicial is not None and formulario.is_valid():
        filtros = formulario.cleaned_data
        argumentos = {
            "sede": filtros["sede"], "cancha": filtros["cancha"], "fecha": filtros["fecha"],
            "hora_seleccionada": filtros["hora"],
            "fecha_maxima": formulario.fecha_maxima,
        }
        datos = construir_agenda(**argumentos)
        if request.method == "POST":
            try:
                detalle = datos["detalle"]
                if detalle is None:
                    raise ValidationError("Seleccioná un turno en la agenda.")
                if accion == "reservar":
                    if not detalle["puede_reservar"]:
                        raise ValidationError(detalle["impedimento"] or "El turno ya está ocupado. Revisá la agenda.")
                    if formulario_reserva.is_valid():
                        disponibilidad = consultar_disponibilidad(detalle["cancha"], detalle["fecha"])
                        turno = next((
                            turno for turno in disponibilidad["turnos"] if turno.hora_inicio == detalle["hora"]
                        ), None)
                        if turno is None:
                            raise ValidationError("El turno ya no está disponible. Revisá la agenda.")
                        reserva = registrar_reserva(
                            request.user, formulario_reserva.cleaned_data["organizador"],
                            detalle["cancha"], detalle["fecha"], turno.pk,
                            formulario_reserva.cleaned_data["precio_mostrado"],
                            formulario_reserva.cleaned_data["observaciones"],
                        )
                        messages.success(request, f"La reserva {reserva.numero} fue registrada.")
                        return redirect(datos["url_seleccion"])
                elif accion in ("anular", "finalizar"):
                    reserva = detalle["reserva"]
                    if reserva is None or request.POST.get("reserva") != str(reserva.pk):
                        raise ValidationError("La actividad del turno cambió. Revisá la agenda antes de confirmar.")
                    if accion == "anular" and formulario_anulacion.is_valid():
                        anular_reserva(request.user, reserva.pk, formulario_anulacion.cleaned_data["motivo"])
                        messages.success(request, f"La reserva {reserva.numero} fue anulada. Su turno quedó liberado.")
                        return redirect(datos["url_seleccion"])
                    if accion == "finalizar":
                        finalizar_reserva(reserva.pk, usuario=request.user)
                        messages.success(request, f"La reserva {reserva.numero} fue finalizada.")
                        return redirect(datos["url_seleccion"])
                else:
                    raise ValidationError("La acción solicitada no es válida.")
            except ValidationError as error:
                for mensaje in error.messages:
                    messages.error(request, mensaje)
                argumentos["sede"].refresh_from_db()
                if argumentos["cancha"] is not None:
                    argumentos["cancha"].refresh_from_db()
                datos = construir_agenda(**argumentos)

    contexto = {
        "formulario": formulario,
        "formulario_reserva": formulario_reserva,
        "formulario_anulacion": formulario_anulacion,
        "hay_sedes": sede_inicial is not None,
        "agenda": datos,
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Agenda", None)],
        "zona_horaria": timezone.get_current_timezone_name(),
    }
    if request.method == "GET" and request.headers.get("X-Agenda-Detalle") == "1":
        if not datos:
            return JsonResponse({"error": "Revisá la sede, fecha y cancha seleccionadas."}, status=400)
        respuesta = render(request, "agenda/_detalle_turno.html", contexto)
        respuesta["X-Agenda-Seleccion"] = datos["url_seleccion"] if datos["detalle"] else datos["url_cerrar"]
        return respuesta
    return render(request, "agenda/agenda.html", contexto)
