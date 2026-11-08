from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AperturaCajaForm, CierreCajaForm, IngresoForm, SeleccionOrigenIngresoForm
from .ingresos import ORIGENES, cobros_del_origen, consultar_origen, registrar_ingreso
from .models import MovimientoFondo, SesionCaja
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
    return render(request, "caja/sesion_detalle.html", {
        "pagina_movimientos": Paginator(sesion.movimientos.all(), 25).get_page(request.GET.get("pagina")),
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
    tipo = request.GET.get("tipo")
    contexto = {"sesion": sesion, "tipo": tipo}
    if tipo is None:
        return render(request, "caja/ingreso_origen.html", contexto)
    if tipo != "general" and tipo not in ORIGENES:
        raise Http404
    origen = None
    if tipo != "general":
        if "origen" not in request.GET:
            contexto["seleccion"] = SeleccionOrigenIngresoForm(tipo=tipo)
            contexto["hay_origenes"] = contexto["seleccion"].fields["origen"].queryset.exists()
            return render(request, "caja/ingreso_origen.html", contexto)
        try:
            origen = consultar_origen(tipo, request.GET.get("origen"))
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("caja:ingreso_crear", pk=pk)
        origen_anulado = origen.evento.estado == "anulado" if tipo == "reserva" else origen.estado == "anulado"
        if origen_anulado and request.method == "GET":
            messages.error(request, "El origen está Anulado y no admite nuevos cobros.")
            return redirect("caja:sesion_detalle", pk=pk)
        contexto.update({
            "origen": origen, "categoria_texto": dict(MovimientoFondo.CategoriaIngreso.choices)[ORIGENES[tipo][2]],
            "importe_aplicado": origen.total if tipo == "reserva" else origen.precio_aplicado,
            "pagina_cobros": Paginator(cobros_del_origen(tipo, origen.pk), 25).get_page(request.GET.get("pagina")),
        })
        parametros = request.GET.copy()
        parametros.pop("pagina", None)
        contexto["parametros"] = parametros.urlencode()
    formulario = IngresoForm(request.POST if request.method == "POST" else None, vinculado=origen is not None)
    contexto["formulario"] = formulario
    if request.method == "POST" and formulario.is_valid():
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
    exigir_acceso_caja(request.user)
    movimiento = get_object_or_404(MovimientoFondo.objects.select_related(
        "sesion", "registrado_por", "plan_usuario__usuario", "plan_usuario__plan",
        "membresia_usuario__usuario", "membresia_usuario__membresia", "reserva__organizador",
    ), pk=pk)
    url_origen = None
    for tipo, (_, campo, _) in ORIGENES.items():
        if getattr(movimiento, campo):
            destino = {"reserva": "reservas:reserva_detalle", "plan": "membresias:contratacion_plan_detalle", "membresia": "membresias:contratacion_membresia_detalle"}[tipo]
            url_origen = reverse(destino, args=[getattr(movimiento, campo)])
            break
    return render(request, "caja/movimiento_detalle.html", {"movimiento": movimiento, "url_origen": url_origen})
