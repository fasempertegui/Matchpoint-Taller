from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import (
    AnulacionMovimientoForm, AperturaCajaForm, CierreCajaForm, HistorialMovimientosForm,
    HistorialSesionesForm, IngresoForm, MovimientoCajaForm, SeleccionOrigenIngresoForm,
)
from .ingresos import ORIGENES, cobros_del_origen, registrar_ingreso
from .models import MovimientoFondo, SesionCaja
from .movimientos import anular_movimiento, registrar_movimiento, revision_anulacion
from .servicios import abrir_caja, cerrar_caja, efectivo_esperado, exigir_acceso_caja, revision_apertura, ultimo_cierre, resumen_sesion


@login_required
@never_cache
@require_GET
def caja_actual(request):
    exigir_acceso_caja(request.user)
    sesion = SesionCaja.objects.filter(estado=SesionCaja.Estado.ABIERTA).first()
    if sesion:
        return redirect("caja:sesion_detalle", pk=sesion.pk)
    return render(request, "caja/caja_actual.html", {"ultimo_cierre": ultimo_cierre()})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def caja_abrir(request):
    actor = exigir_acceso_caja(request.user)
    sesion = SesionCaja.objects.filter(estado=SesionCaja.Estado.ABIERTA).first()
    if sesion:
        messages.info(request, "Ya existe una sesión abierta.")
        return redirect("caja:sesion_detalle", pk=sesion.pk)
    cierre = ultimo_cierre()
    formulario = AperturaCajaForm(request.POST if request.method == "POST" else None, initial={"revision": revision_apertura(actor, cierre)})
    if request.method == "POST" and formulario.is_valid():
        try:
            sesion = abrir_caja(actor, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error.messages)
            datos = formulario.data.copy()
            datos["revision"] = revision_apertura(actor, ultimo_cierre())
            formulario.data = datos
        else:
            messages.success(request, f"La caja {sesion.numero} está abierta.")
            return redirect("caja:sesion_detalle", pk=sesion.pk)
    return render(request, "caja/sesion_formulario.html", {"formulario": formulario, "ultimo_cierre": ultimo_cierre(), "titulo": "Abrir caja"})


@login_required
@never_cache
@require_GET
def sesion_detalle(request, pk):
    actor = exigir_acceso_caja(request.user)
    sesion = get_object_or_404(SesionCaja.objects.select_related("responsable"), pk=pk)
    pagina = Paginator(sesion.movimientos.all(), 25).get_page(request.GET.get("pagina"))
    if sesion.estado == "cerrada":
        for movimiento in pagina:
            movimiento.incluido_al_cierre = movimiento.anulado_en is None or movimiento.anulado_en > sesion.cerrada_en
    return render(request, "caja/sesion_detalle.html", {
        "pagina_movimientos": pagina,
        **resumen_sesion(sesion),
        "sesion": sesion, "esperado": efectivo_esperado(sesion) if sesion.estado == SesionCaja.Estado.ABIERTA else sesion.efectivo_esperado,
        "puede_cerrar": sesion.estado == SesionCaja.Estado.ABIERTA and sesion.responsable_id == actor.pk,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def caja_cerrar(request, pk):
    actor = exigir_acceso_caja(request.user)
    sesion = get_object_or_404(SesionCaja, pk=pk)
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    if sesion.estado != SesionCaja.Estado.ABIERTA:
        messages.info(request, "La sesión ya está cerrada.")
        return redirect("caja:sesion_detalle", pk=pk)
    formulario = CierreCajaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and formulario.is_valid():
        try:
            cerrar_caja(actor, pk, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error.messages)
        else:
            messages.success(request, f"La caja {sesion.numero} fue cerrada.")
            return redirect("caja:sesion_detalle", pk=pk)
    return render(request, "caja/sesion_formulario.html", {"formulario": formulario, "sesion": sesion, "esperado": efectivo_esperado(sesion), "titulo": "Cerrar caja", **resumen_sesion(sesion)})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def ingreso_crear(request, pk):
    actor = exigir_acceso_caja(request.user)
    sesion = get_object_or_404(SesionCaja, pk=pk)
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    if sesion.estado != SesionCaja.Estado.ABIERTA and request.method == "GET":
        messages.error(request, "La sesión está cerrada y no admite ingresos nuevos.")
        return redirect("caja:sesion_detalle", pk=pk)
    paso = request.POST.get("paso", "")
    tipo = request.POST.get("tipo") or request.GET.get("tipo")
    tipo_previo = tipo
    if paso == "volver_tipo":
        tipo = None
    datos = request.POST if request.method == "POST" else request.GET
    borrador = {nombre: request.POST[nombre] for nombre in IngresoForm.base_fields if nombre in request.POST}
    contexto = {
        "sesion": sesion, "tipo": tipo, "tipo_previo": tipo_previo, "borrador": borrador,
        "opciones_origen": [
            ("reserva", "Reserva", "Cobrá un turno de cancha"),
            ("plan", "Contratación de plan", "Cobrá un plan contratado"),
            ("membresia", "Contratación de membresía", "Cobrá una membresía contratada"),
            ("general", "Ingreso sin vínculo", "Registrá cobros en general"),
        ],
        "numero_paso": 1, "total_pasos": 3, "nombre_paso": "Origen del ingreso",
    }
    if tipo is None:
        return render(request, "caja/ingreso_origen.html", contexto)
    if tipo != "general" and tipo not in ORIGENES:
        raise Http404
    contexto["tipo_texto"] = dict((valor, nombre) for valor, nombre, _ in contexto["opciones_origen"])[tipo]
    contexto["total_pasos"] = 2 if tipo == "general" else 3
    origen = None
    if tipo != "general":
        seleccion = SeleccionOrigenIngresoForm(datos if datos.get("origen") else None, tipo=tipo)
        contexto.update({"seleccion": seleccion, "numero_paso": 2, "nombre_paso": "Seleccionar registro"})
        if paso in ("volver", "buscar") or "pagina_origen" in datos or not datos.get("origen") or not seleccion.is_valid():
            consulta = seleccion.fields["origen"].queryset
            busqueda = datos.get("q", "").strip()[:100]
            persona = "organizador" if tipo == "reserva" else "usuario"
            for termino in busqueda.split():
                filtro = Q(**{f"{persona}__first_name__icontains": termino}) | Q(**{f"{persona}__last_name__icontains": termino}) | Q(**{f"{persona}__username__icontains": termino})
                if tipo == "reserva":
                    filtro |= Q(evento__turno__cancha__nombre__icontains=termino) | Q(evento__turno__cancha__sede__nombre__icontains=termino)
                    numero = termino.upper().removeprefix("R-")
                    if numero.isascii() and numero.isdigit() and len(numero) <= 18:
                        filtro |= Q(pk=int(numero))
                else:
                    filtro |= Q(**{f"{tipo}__nombre__icontains": termino})
                consulta = consulta.filter(filtro)
            contexto.update({
                "busqueda": busqueda,
                "registros": Paginator(consulta.order_by("-pk"), 8).get_page(datos.get("pagina_origen")),
                "origen_seleccionado": str(datos.get("origen", "")),
            })
            return render(request, "caja/ingreso_origen.html", contexto)
        origen = seleccion.cleaned_data["origen"]
        contexto.update({
            "origen": origen, "categoria_texto": dict(MovimientoFondo.CategoriaIngreso.choices)[ORIGENES[tipo][2]],
            "importe_aplicado": origen.total if tipo == "reserva" else origen.precio_aplicado,
            "pagina_cobros": Paginator(cobros_del_origen(tipo, origen.pk), 25).get_page(request.GET.get("pagina")),
        })
        parametros = request.GET.copy()
        parametros["origen"] = origen.pk
        parametros.pop("pagina", None)
        contexto["parametros"] = parametros.urlencode()
    contexto.update({"numero_paso": contexto["total_pasos"], "nombre_paso": "Datos del cobro"})
    registrar = request.method == "POST" and paso == "registrar"
    formulario = IngresoForm(request.POST if registrar else None, initial=borrador)
    formulario.fields["concepto"].widget = forms.TextInput(attrs={"class": "form-control"})
    formulario.fields["referencia"].widget.attrs["placeholder"] = "8D0Q619L3VV1L8KVN7JZ5R"
    contexto["formulario"] = formulario
    if registrar and formulario.is_valid():
        try:
            movimiento = registrar_ingreso(actor, pk, tipo_origen=tipo, origen_id=origen.pk if origen else None, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error.messages)
        else:
            messages.success(request, f"El ingreso {movimiento.numero} está registrado.")
            return redirect("caja:movimiento_detalle", pk=movimiento.pk)
    return render(request, "caja/ingreso_formulario.html", contexto)


@login_required
@never_cache
@require_GET
def movimiento_detalle(request, pk):
    actor = exigir_acceso_caja(request.user)
    movimiento = get_object_or_404(MovimientoFondo.objects.select_related(
        "sesion", "registrado_por", "anulado_por", "plan_usuario__usuario", "plan_usuario__plan",
        "membresia_usuario__usuario", "membresia_usuario__membresia", "reserva__organizador",
    ), pk=pk)
    url_origen = None
    for tipo, (_, campo, _) in ORIGENES.items():
        if getattr(movimiento, campo):
            destino = {"reserva": "reservas:reserva_detalle", "plan": "membresias:contratacion_plan_detalle", "membresia": "membresias:contratacion_membresia_detalle"}[tipo]
            url_origen = reverse(destino, args=[getattr(movimiento, campo)])
            break
    actual = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
    return render(request, "caja/movimiento_detalle.html", {
        "movimiento": movimiento, "url_origen": url_origen,
        "puede_anular": actual is not None and movimiento.estado == "vigente",
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def movimiento_crear(request, pk):
    actor = exigir_acceso_caja(request.user)
    sesion = get_object_or_404(SesionCaja, pk=pk)
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    if sesion.estado != "abierta" and request.method == "GET":
        messages.error(request, "La sesión está cerrada y no admite movimientos nuevos.")
        return redirect("caja:sesion_detalle", pk=pk)
    clase = request.GET.get("clase")
    if clase is None:
        return render(request, "caja/movimiento_tipo.html", {"sesion": sesion})
    if clase not in ("egreso", "aporte", "retiro"):
        raise Http404
    formulario = MovimientoCajaForm(request.POST if request.method == "POST" else None, clase=clase)
    if request.method == "POST" and formulario.is_valid():
        try:
            movimiento = registrar_movimiento(actor, pk, clase=clase, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error.messages)
        else:
            messages.success(request, f"El movimiento {movimiento.numero} está registrado.")
            return redirect("caja:movimiento_detalle", pk=movimiento.pk)
    return render(request, "caja/movimiento_formulario.html", {
        "sesion": sesion, "formulario": formulario, "clase": clase,
        "titulo": f"Registrar {dict(MovimientoFondo.Clase.choices)[clase].lower()}",
        "disponible": efectivo_esperado(sesion),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def movimiento_anular(request, pk):
    actor = exigir_acceso_caja(request.user)
    actual = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
    if actual is None:
        raise PermissionDenied
    movimiento = get_object_or_404(MovimientoFondo.objects.select_related("sesion"), pk=pk)
    if movimiento.estado != "vigente" and request.method == "GET":
        messages.info(request, "El movimiento ya está Anulado.")
        return redirect("caja:movimiento_detalle", pk=pk)
    formulario = AnulacionMovimientoForm(request.POST if request.method == "POST" else None, initial={"revision": revision_anulacion(actor, movimiento, actual)})
    if request.method == "POST" and formulario.is_valid():
        try:
            anular_movimiento(actor, pk, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error.messages)
        else:
            messages.success(request, "El movimiento fue Anulado. Sus datos originales se conservan.")
            return redirect("caja:movimiento_detalle", pk=pk)
    origen = movimiento.sesion
    return render(request, "caja/movimiento_anular.html", {
        "movimiento": movimiento, "actual": actual, "formulario": formulario,
        "efecto": -movimiento.efecto_efectivo,
        "esperado_resultante": efectivo_esperado(origen) - movimiento.efecto_efectivo if origen.estado == "abierta" else None,
    })


def _filtrar_fechas(consulta, datos):
    if datos.get("desde"):
        consulta = consulta.filter(creado_en__date__gte=datos["desde"])
    if datos.get("hasta"):
        consulta = consulta.filter(creado_en__date__lte=datos["hasta"])
    return consulta


@login_required
@never_cache
@require_GET
def historial_sesiones(request):
    exigir_acceso_caja(request.user)
    formulario = HistorialSesionesForm(request.GET)
    consulta = SesionCaja.objects.select_related("responsable").none()
    if formulario.is_valid():
        datos = formulario.cleaned_data
        consulta = _filtrar_fechas(SesionCaja.objects.select_related("responsable"), datos)
        if datos.get("estado"):
            consulta = consulta.filter(estado=datos["estado"])
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "caja/historial.html", {
        "formulario": formulario, "pagina": Paginator(consulta, 25).get_page(request.GET.get("pagina")),
        "parametros": parametros.urlencode(), "sesiones": True, "titulo": "Historial de sesiones",
    })


@login_required
@never_cache
@require_GET
def movimiento_lista(request):
    exigir_acceso_caja(request.user)
    formulario = HistorialMovimientosForm(request.GET)
    consulta = MovimientoFondo.objects.none()
    if formulario.is_valid():
        datos = formulario.cleaned_data
        consulta = _filtrar_fechas(MovimientoFondo.objects.all(), datos)
        for campo in ("sesion", "clase", "medio_pago", "estado"):
            if datos.get(campo):
                consulta = consulta.filter(**{campo: datos[campo]})
        if datos.get("categoria"):
            clase, categoria = datos["categoria"].split(":")
            consulta = consulta.filter(**{f"categoria_{clase}": categoria})
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(request, "caja/historial.html", {
        "formulario": formulario, "pagina": Paginator(consulta, 25).get_page(request.GET.get("pagina")),
        "parametros": parametros.urlencode(), "titulo": "Movimientos de caja",
    })
