from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_headers

from bloqueos.forms import BloqueoAnulacionForm, BloqueoForm
from bloqueos.servicios import anular_bloqueo, registrar_bloqueo
from instalaciones.models import Sede
from reservas.disponibilidad import consultar_disponibilidad
from reservas.forms import ReservaAnulacionForm
from reservas.servicios import anular_reserva, exigir_acceso_reservas, finalizar_reserva, registrar_reserva

from .forms import AgendaFiltroForm, AgendaOperacionForm, AgendaReservaForm
from .operaciones import ejecutar_operacion, preparar_operacion
from .servicios import construir_agenda, enlace_agenda


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
    panel_acciones = request.GET.get("panel") == "acciones"
    contexto_acciones = {}
    accion = request.POST.get("accion") if request.method == "POST" else None
    formulario_reserva = AgendaReservaForm(request.POST if accion == "reservar" else None)
    formulario_anulacion = ReservaAnulacionForm(request.POST if accion == "anular" else None)
    formulario_bloqueo = None
    formulario_liberacion = None
    datos = {}
    if sede_inicial is not None and formulario.is_valid():
        filtros = formulario.cleaned_data
        argumentos = {
            "sede": filtros["sede"], "cancha": filtros["cancha"], "fecha": filtros["fecha"],
            "hora_seleccionada": None if panel_acciones else filtros["hora"],
            "fecha_maxima": formulario.fecha_maxima,
        }
        datos = construir_agenda(**argumentos)
        detalle = datos["detalle"]
        if detalle is not None:
            formulario_bloqueo = BloqueoForm(
                request.POST if accion == "bloquear" else None,
                prefix="bloqueo",
                anula_reserva=detalle["reserva"] is not None,
                initial={"evento_esperado": detalle["evento"].pk if detalle["evento"] else 0},
            )
            formulario_liberacion = BloqueoAnulacionForm(
                request.POST if accion == "liberar_bloqueo" else None,
                prefix="liberacion",
                initial={"bloqueo": detalle["bloqueo"].pk if detalle["bloqueo"] else None},
            )
        if panel_acciones:
            contexto_acciones = _preparar_acciones_dia(request, filtros["sede"], filtros["fecha"])
            if isinstance(contexto_acciones, HttpResponseRedirect):
                return contexto_acciones
            if request.method == "POST" and request.POST.get("paso") == "confirmar":
                datos = construir_agenda(**argumentos)
        elif request.method == "POST":
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
                elif accion == "bloquear":
                    if not detalle["puede_bloquear"]:
                        raise ValidationError("El turno seleccionado no admite un nuevo bloqueo. Revisá la agenda.")
                    if formulario_bloqueo.is_valid():
                        valores = formulario_bloqueo.cleaned_data
                        bloqueo = registrar_bloqueo(
                            request.user, detalle["cancha"], detalle["fecha"], detalle["hora"],
                            valores["motivo"], valores["observaciones"], valores["evento_esperado"],
                            valores.get("motivo_anulacion", ""),
                        )
                        messages.success(request, f"El bloqueo {bloqueo.numero} fue registrado.")
                        return redirect(datos["url_seleccion"])
                elif accion == "liberar_bloqueo":
                    if not detalle["puede_liberar_bloqueo"]:
                        raise ValidationError("El turno seleccionado no tiene un bloqueo que pueda anularse.")
                    if formulario_liberacion.is_valid():
                        valores = formulario_liberacion.cleaned_data
                        if valores["bloqueo"] != detalle["bloqueo"].pk:
                            raise ValidationError("La actividad del turno cambió. Revisá la agenda antes de confirmar.")
                        bloqueo = anular_bloqueo(
                            request.user, valores["bloqueo"], valores["motivo"],
                            detalle["cancha"], detalle["fecha"], detalle["hora"],
                        )
                        messages.success(request, f"El bloqueo {bloqueo.numero} fue anulado. Su turno quedó liberado.")
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
        "formulario_bloqueo": formulario_bloqueo,
        "formulario_liberacion": formulario_liberacion,
        "hay_sedes": sede_inicial is not None,
        "agenda": datos,
        "panel_acciones": panel_acciones,
        **contexto_acciones,
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Agenda", None)],
        "zona_horaria": timezone.get_current_timezone_name(),
    }
    if request.headers.get("X-Agenda-Detalle") == "1":
        if not datos:
            return JsonResponse({"error": "Revisá la sede, fecha y cancha seleccionadas."}, status=400)
        plantilla = "agenda/_acciones_dia.html" if panel_acciones else "agenda/_detalle_turno.html"
        respuesta = render(request, plantilla, contexto)
        respuesta["X-Agenda-Seleccion"] = (
            datos["url_acciones"] if panel_acciones else
            datos["url_seleccion"] if datos["detalle"] else datos["url_cerrar"]
        )
        return respuesta
    return render(request, "agenda/agenda.html", contexto)


def _preparar_acciones_dia(request, sede, fecha):
    avisos = []
    url_agenda = enlace_agenda(sede, fecha)
    paso = request.POST.get("paso") if request.method == "POST" else None
    datos = request.POST if request.method == "POST" else None
    confirmacion = None
    if paso in ("editar", "confirmar"):
        try:
            confirmacion = signing.loads(
                request.POST.get("confirmacion", ""), salt="agenda.acciones-dia", max_age=900,
            )
            if (confirmacion["usuario"], confirmacion["sede"], confirmacion["fecha"]) != (
                request.user.pk, sede.pk, fecha.isoformat(),
            ):
                raise signing.BadSignature
            datos = QueryDict(mutable=True)
            for nombre, valor in confirmacion["parametros"].items():
                if isinstance(valor, list):
                    datos.setlist(nombre, [str(item) for item in valor])
                elif isinstance(valor, bool):
                    if valor:
                        datos[nombre] = "on"
                else:
                    datos[nombre] = valor
            canchas = confirmacion["parametros"]["canchas"]
            if set(canchas) == set(sede.canchas.values_list("pk", flat=True)):
                datos["seleccion_canchas"] = "todas"
            else:
                datos["seleccion_canchas"] = "seleccionar"
            datos["horario"] = confirmacion["parametros"]["hora_desde"] or "dia"
        except signing.BadSignature:
            avisos.append("La vista previa venció o no corresponde a esta selección. Preparala nuevamente.")
            datos = None
            paso = None

    formulario = AgendaOperacionForm(datos, sede=sede, fecha=fecha)
    previa = None
    token = None
    parametros = None
    if paso not in (None, "editar", "previsualizar", "confirmar"):
        formulario.is_valid()
        formulario.add_error(None, "La acción solicitada no es válida.")
    elif paso is not None and formulario.is_valid():
        parametros = formulario.parametros()
        try:
            if paso == "confirmar":
                try:
                    resultado = ejecutar_operacion(request.user, sede.pk, fecha, parametros, confirmacion["huella"])
                except ValidationError as error:
                    for mensaje in error.messages:
                        avisos.append(mensaje)
                    sede.refresh_from_db()
                else:
                    messages.success(
                        request,
                        f'La operación fue completada: {resultado["anulaciones"]} eventos anulados '
                        f'y {resultado["bloqueos_a_crear"]} bloqueos creados.',
                    )
                    return redirect(url_agenda)
            if paso != "editar":
                previa = preparar_operacion(sede, fecha, parametros)
                if not formulario.validar_motivos(previa):
                    previa = None
        except ValidationError as error:
            for mensaje in error.messages:
                formulario.add_error(None, mensaje)
    if previa is not None:
        token = signing.dumps({
            "usuario": request.user.pk, "sede": sede.pk, "fecha": fecha.isoformat(),
            "parametros": parametros, "huella": previa["huella"],
        }, salt="agenda.acciones-dia", compress=True)
    return {
        "sede": sede, "fecha": fecha,
        "formulario_operacion": formulario, "previa": previa, "confirmacion": token, "parametros_operacion": parametros,
        "avisos_operacion": avisos,
        "motivo_bloqueo": dict(formulario.fields["motivo_bloqueo"].choices).get(parametros["motivo_bloqueo"], "")
            if parametros else "",
    }
