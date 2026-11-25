from calendar import monthrange
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.vary import vary_on_headers

from bloqueos.forms import BloqueoAnulacionForm, BloqueoForm
from bloqueos.models import Bloqueo
from bloqueos.servicios import anular_bloqueo, registrar_bloqueo, validar_anulacion_bloqueo
from clases.forms import ClaseTurnoForm
from clases.permisos import exigir_acceso_clases, exigir_administracion_clases
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda, opciones_meses_agenda
from common.modales import es_peticion_modal, respuesta_modal_exito, respuesta_modal_html
from instalaciones.models import Sede
from reservas.models import Evento
from reservas.servicios import exigir_acceso_reservas, finalizar_reserva
from usuarios.models import Rol

from .forms import AgendaFiltroForm, AgendaMesForm, AgendaOperacionForm, AgendaOperacionMesForm, AgendaReservaForm
from .operaciones import ejecutar_operacion, preparar_operacion
from .servicios import construir_agenda, enlace_acciones, enlace_agenda


def _destino_seguro(valor, defecto):
    if valor and valor.startswith("/") and not valor.startswith("//"):
        return valor
    return defecto


@login_required
@never_cache
@require_GET
def buscar_organizadores(request):
    if not exigir_acceso_reservas(request.user):
        raise PermissionDenied
    busqueda = request.GET.get("q", "").strip()[:100]
    if len(busqueda) < 2:
        return JsonResponse({"resultados": [], "hay_mas": False})
    personas = AgendaReservaForm(es_administrador=True).fields["organizador"].queryset
    for termino in busqueda.split():
        personas = personas.filter(
            Q(first_name__icontains=termino) | Q(last_name__icontains=termino)
            | Q(username__icontains=termino)
        )
    filas = list(personas.order_by("first_name", "last_name", "username", "pk")[:11])
    return JsonResponse({
        "resultados": [
            {"id": persona.pk, "nombre": str(persona), "usuario": persona.username}
            for persona in filas[:10]
        ],
        "hay_mas": len(filas) > 10,
    })


@login_required
@never_cache
@vary_on_headers("X-Agenda-Detalle")
@require_http_methods(["GET", "POST"])
def agenda(request):
    usuario = exigir_acceso_clases(request.user)
    es_administrador = usuario.tiene_rol(Rol.ADMINISTRADOR)
    if request.method == "POST":
        exigir_acceso_reservas(usuario)
    panel_historial = request.GET.get("panel") == "historial" and request.method == "GET"
    accion = request.POST.get("accion") if request.method == "POST" else None
    if request.method == "POST" and (not es_administrador or accion != "finalizar"):
        raise PermissionDenied

    parametros = request.GET.copy()
    parametros.setdefault("fecha", timezone.localdate().isoformat())
    sede_inicial = Sede.objects.order_by("estado", "nombre").first()
    if sede_inicial is not None:
        parametros.setdefault("sede", str(sede_inicial.pk))
    formulario = AgendaFiltroForm(parametros)
    datos = {}
    if sede_inicial is not None and formulario.is_valid():
        filtros = formulario.cleaned_data
        argumentos = {
            "sede": filtros["sede"], "cancha": filtros["cancha"], "fecha": filtros["fecha"],
            "hora_seleccionada": filtros["hora"],
            "fecha_maxima": formulario.fecha_maxima,
            "usuario": usuario, "es_administrador": es_administrador,
            "historial": panel_historial,
        }
        datos = construir_agenda(**argumentos)
        if request.method == "POST":
            try:
                detalle = datos["detalle"]
                if detalle is None:
                    raise ValidationError("Seleccioná un turno en la agenda.")
                reserva = detalle["reserva"]
                if reserva is None or request.POST.get("reserva") != str(reserva.pk):
                    raise ValidationError("La actividad del turno cambió. Revisá la agenda antes de confirmar.")
                finalizar_reserva(reserva.pk, usuario=request.user)
                messages.success(request, f"La reserva {reserva.numero} fue finalizada.")
                return redirect(datos["url_seleccion"])
            except ValidationError as error:
                for mensaje in error.messages:
                    messages.error(request, mensaje)
                argumentos["sede"].refresh_from_db()
                if argumentos["cancha"] is not None:
                    argumentos["cancha"].refresh_from_db()
                datos = construir_agenda(**argumentos)

    contexto = {
        "formulario": formulario,
        "hay_sedes": sede_inicial is not None,
        "agenda": datos,
        "panel_historial": panel_historial,
        "zona_horaria": timezone.get_current_timezone_name(),
        "es_administrador": es_administrador,
    }
    if request.headers.get("X-Agenda-Detalle") == "1":
        if not datos:
            return JsonResponse({"error": "Revisá la sede, fecha y cancha seleccionadas."}, status=400)
        plantilla = "agenda/_historial_turno.html" if panel_historial else "agenda/_detalle_turno.html"
        respuesta = render(request, plantilla, contexto)
        respuesta["X-Agenda-Seleccion"] = (
            datos["url_historial"] if panel_historial and datos["detalle"] else
            datos["url_seleccion"] if datos["detalle"] else datos["url_cerrar"]
        )
        return respuesta
    return render(request, "agenda/agenda.html", contexto)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def bloqueo_crear(request):
    usuario = exigir_administracion_clases(request.user)
    ubicacion = ClaseTurnoForm(request.GET)
    url_agenda = reverse("agenda:agenda")
    destino = _destino_seguro(request.POST.get("siguiente") or request.GET.get("siguiente"), url_agenda)
    if not es_peticion_modal(request):
        return redirect(destino)

    if not ubicacion.is_valid():
        messages.error(request, "El turno seleccionado no admite un nuevo bloqueo. Revisá la agenda.")
        return respuesta_modal_exito(destino)

    cancha = ubicacion.cleaned_data["cancha"]
    fecha = ubicacion.cleaned_data["fecha"]
    hora = time(ubicacion.cleaned_data["hora"])
    fin = (datetime.combine(fecha, hora) + timedelta(hours=1)).time()
    url_turno = enlace_agenda(cancha.sede, fecha, cancha, hora.hour)
    destino = _destino_seguro(request.POST.get("siguiente") or request.GET.get("siguiente"), url_turno)

    evento_actual = Evento.objects.filter(
        turno__cancha=cancha, turno__fecha=fecha, turno__hora_inicio=hora,
    ).exclude(estado=Evento.Estado.ANULADO).select_related("reserva__organizador").first()
    reserva = getattr(evento_actual, "reserva", None) if evento_actual and evento_actual.tipo == Evento.Tipo.RESERVA else None
    if evento_actual is not None and reserva is None:
        messages.error(request, "El turno seleccionado no admite un nuevo bloqueo desde esta acción.")
        return respuesta_modal_exito(destino)

    formulario = BloqueoForm(
        request.POST if request.method == "POST" else None,
        initial={"evento_esperado": evento_actual.pk if evento_actual else 0},
    )
    if request.method == "POST" and formulario.is_valid():
        valores = formulario.cleaned_data
        try:
            bloqueo = registrar_bloqueo(
                usuario,
                cancha,
                fecha,
                hora,
                valores["motivo"],
                valores["observaciones"],
                valores["evento_esperado"],
                usar_motivo_bloqueo=True,
            )
            messages.success(request, f"El bloqueo {bloqueo.numero} fue registrado.")
            return respuesta_modal_exito(destino)
        except ValidationError as error:
            formulario.add_error(None, error)

    accion_url = reverse("agenda:bloqueo_crear") + "?" + urlencode({
        "cancha": cancha.pk, "fecha": fecha.isoformat(), "hora": hora.hour,
    })
    return respuesta_modal_html(
        request,
        "agenda/_modal_bloqueo_crear.html",
        {
            "cancha": cancha,
            "fecha": fecha,
            "hora": hora,
            "fin": fin,
            "reserva": reserva,
            "formulario": formulario,
            "accion_url": accion_url,
            "siguiente": destino,
        },
        status=400 if formulario.errors else 200,
        peligro=reserva is not None,
        amplio=True,
        errores=bool(formulario.errors),
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def bloqueo_anular(request, pk):
    usuario = exigir_administracion_clases(request.user)
    bloqueo = get_object_or_404(
        Bloqueo.objects.select_related("evento__turno__cancha__sede"),
        pk=pk, evento__tipo="bloqueo",
    )
    url_detalle = reverse("agenda:bloqueo_detalle", args=[bloqueo.pk])
    destino = _destino_seguro(request.POST.get("siguiente") or request.GET.get("siguiente"), url_detalle)
    if not es_peticion_modal(request):
        return redirect(destino)

    try:
        validar_anulacion_bloqueo(bloqueo, timezone.localtime())
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return respuesta_modal_exito(destino)

    turno = bloqueo.evento.turno
    formulario = BloqueoAnulacionForm(
        request.POST if request.method == "POST" else None,
        initial={"bloqueo": bloqueo.pk},
    )
    if request.method == "POST" and formulario.is_valid():
        valores = formulario.cleaned_data
        try:
            bloqueo = anular_bloqueo(
                usuario,
                valores["bloqueo"],
                valores["motivo"],
                turno.cancha,
                turno.fecha,
                turno.hora_inicio,
            )
            messages.success(request, f"El bloqueo {bloqueo.numero} fue anulado. Su turno quedó liberado.")
            return respuesta_modal_exito(destino)
        except ValidationError as error:
            formulario.add_error(None, error)

    return respuesta_modal_html(
        request,
        "agenda/_modal_bloqueo_anular.html",
        {
            "bloqueo": bloqueo,
            "turno": turno,
            "formulario": formulario,
            "siguiente": destino if destino != url_detalle else "",
        },
        status=400 if formulario.errors else 200,
        peligro=True,
        amplio=True,
        errores=bool(formulario.errors),
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def agenda_acciones(request):
    exigir_administracion_clases(request.user)
    hoy = timezone.localdate()
    mensual = request.GET.get("tipo") == "mes"

    sede_inicial = Sede.objects.order_by("estado", "nombre").first()
    parametros = request.GET.copy()
    parametros.setdefault("fecha", hoy.isoformat())
    if sede_inicial is not None:
        parametros.setdefault("sede", str(sede_inicial.pk))
    filtro = AgendaFiltroForm(parametros)
    if sede_inicial is not None and filtro.is_valid():
        sede = filtro.cleaned_data["sede"]
        cancha = filtro.cleaned_data["cancha"]
        fecha = filtro.cleaned_data["fecha"]
    else:
        sede = sede_inicial
        cancha = None
        fecha = hoy
    if fecha < hoy and not mensual:
        fecha = hoy

    url_agenda = enlace_agenda(sede, fecha, cancha) if sede is not None else reverse("agenda:agenda")
    url_tab_dia = enlace_acciones(sede, fecha, cancha, mensual=False) if sede is not None else reverse("agenda:acciones") + "?tipo=dia"
    url_tab_mes = enlace_acciones(sede, fecha, cancha, mensual=True) if sede is not None else reverse("agenda:acciones") + "?tipo=mes"

    contexto = {
        "mensual": mensual,
        "fecha": fecha,
        "hoy": hoy,
        "fecha_minima": hoy.isoformat(),
        "fecha_maxima": fecha_maxima_agenda().isoformat(),
        "sede": sede,
        "cancha": cancha,
        "url_agenda": url_agenda,
        "url_tab_dia": url_tab_dia,
        "url_tab_mes": url_tab_mes,
    }

    if mensual:
        parametros_mes = request.GET.copy()
        mes_inicial = fecha.strftime("%Y-%m")
        if mes_inicial not in dict(opciones_meses_agenda()):
            mes_inicial = hoy.strftime("%Y-%m")
        parametros_mes.setdefault("mes", mes_inicial)
        formulario_mes = AgendaMesForm(parametros_mes)
        contexto["formulario_mes"] = formulario_mes
        if formulario_mes.is_valid():
            mes = formulario_mes.cleaned_data["mes"]
            fin = mes.replace(day=monthrange(mes.year, mes.month)[1])
            url_actual = enlace_acciones(sede, fecha, cancha, mensual=True, mes=mes) if sede is not None else reverse("agenda:acciones") + "?tipo=mes"
            contexto["url_operacion"] = url_actual
            operacion = _preparar_acciones(request, mes, url_agenda, fin)
            if isinstance(operacion, HttpResponseRedirect):
                return operacion
            contexto.update(operacion)
    else:
        contexto["url_operacion"] = url_tab_dia
        operacion = _preparar_acciones(request, fecha, url_agenda)
        if isinstance(operacion, HttpResponseRedirect):
            return operacion
        contexto.update(operacion)

    return render(request, "agenda/acciones_masivas.html", contexto)


def _preparar_acciones(request, fecha, url_agenda, fecha_hasta=None):
    mensual = fecha_hasta is not None
    sal = "agenda.acciones-mes" if mensual else "agenda.acciones-dia"
    paso = request.POST.get("paso") if request.method == "POST" else None
    datos = request.POST if request.method == "POST" else None
    confirmacion = None
    if paso in ("editar", "confirmar"):
        try:
            confirmacion = signing.loads(
                request.POST.get("confirmacion", ""), salt=sal, max_age=900,
            )
            if (confirmacion["usuario"], confirmacion["fecha"]) != (request.user.pk, fecha.isoformat()):
                raise signing.BadSignature
            if mensual and confirmacion.get("fecha_hasta") != fecha_hasta.isoformat():
                raise signing.BadSignature
            if not {"actividades", "seleccion_sedes", "sedes", "seleccion_canchas", "canchas"} <= confirmacion["parametros"].keys():
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
            datos["horario"] = confirmacion["parametros"]["hora_desde"] or "dia"
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            messages.error(request, "La vista previa venció o no corresponde a esta selección. Revisá y prepará la operación nuevamente.")
            datos = None
            paso = None

    clase_formulario = AgendaOperacionMesForm if mensual else AgendaOperacionForm
    formulario = clase_formulario(datos, fecha=fecha)
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
                    if parametros != confirmacion["parametros"]:
                        raise ValidationError("El alcance cambió desde la vista previa. Revisá nuevamente las acciones.")
                    resultado = ejecutar_operacion(request.user, fecha, parametros, confirmacion["huella"], fecha_hasta)
                except ValidationError as error:
                    motivos = " ".join(mensaje.strip() for mensaje in error.messages if mensaje and mensaje.strip())
                    if motivos and "revis" not in motivos.casefold():
                        motivos = f"{motivos} Revisá la vista previa antes de confirmar."
                    messages.error(request, motivos or "No se pudo ejecutar la operación. Revisá la vista previa antes de confirmar.")
                else:
                    messages.success(
                        request,
                        f'La operación fue completada: {resultado["anulaciones"]} eventos anulados '
                        + (f'y {resultado["bloqueos_a_crear"]} bloqueos creados.' if not mensual else 'y sus turnos liberados.'),
                    )
                    return redirect(url_agenda)
            if paso != "editar":
                previa = preparar_operacion(fecha, parametros, fecha_hasta)
                if not formulario.validar_motivos(previa):
                    previa = None
        except ValidationError as error:
            for mensaje in error.messages:
                formulario.add_error(None, mensaje)
    if previa is not None:
        token = signing.dumps({
            "usuario": request.user.pk, "fecha": fecha.isoformat(),
            "parametros": parametros, "huella": previa["huella"],
            "fecha_hasta": fecha_hasta.isoformat() if mensual else None,
        }, salt=sal, compress=True)
    alcance = {}
    if previa is not None:
        alcance["horario"] = "Día completo"
        if parametros["alcance"] == "desde":
            alcance["horario"] = f'Desde las {parametros["hora_desde"]}'
            if parametros["hora_hasta"]:
                alcance["horario"] += f' hasta las {parametros["hora_hasta"]}'
        alcance["actividades"] = [
            etiqueta for valor, etiqueta in formulario.fields["actividades"].choices
            if valor in parametros["actividades"]
        ]
        if mensual:
            alcance.update({
                "desde": previa["desde"],
                "hasta": previa["hasta"],
                "dias": [
                    etiqueta for valor, etiqueta in formulario.fields["dias_semana"].choices
                    if int(valor) in parametros.get("dias_semana", ())
                ] or ["Todos los días"],
            })
    return {
        "fecha": fecha, "mensual": mensual,
        "formulario_operacion": formulario, "previa": previa, "confirmacion": token, "parametros_operacion": parametros,
        "alcance_operacion": alcance,
        "motivo_bloqueo": dict(formulario.fields["motivo_bloqueo"].choices).get(parametros["motivo_bloqueo"], "")
            if parametros and not mensual else "",
    }


@login_required
@never_cache
@require_GET
def bloqueo_detalle(request, pk):
    exigir_administracion_clases(request.user)
    bloqueo = get_object_or_404(
        Bloqueo.objects.select_related(
            "evento__turno__cancha__sede", "evento__registrado_por", "evento__anulado_por",
            "evento_origen__reserva", "evento_origen__clase",
        ),
        pk=pk, evento__tipo="bloqueo",
    )
    turno = bloqueo.evento.turno
    try:
        validar_anulacion_bloqueo(bloqueo, timezone.localtime())
    except ValidationError:
        puede_anular = False
    else:
        puede_anular = True
    return render(request, "agenda/bloqueo_detalle.html", {
        "bloqueo": bloqueo, "turno": turno,
        "puede_anular": puede_anular,
        "url_agenda": enlace_agenda(turno.cancha.sede, turno.fecha, turno.cancha, turno.hora_inicio.hour),
    })
