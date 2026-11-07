from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AperturaCajaForm, CierreCajaForm
from .models import SesionCaja
from .servicios import abrir_caja, cerrar_caja, efectivo_esperado, exigir_acceso_caja, revision_apertura, ultimo_cierre


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
            formulario.add_error(None, error)
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
            formulario.add_error(None, error)
        else:
            messages.success(request, f"La caja {sesion.numero} fue cerrada.")
            return redirect("caja:sesion_detalle", pk=pk)
    return render(request, "caja/sesion_formulario.html", {"formulario": formulario, "sesion": sesion, "esperado": efectivo_esperado(sesion), "titulo": "Cerrar caja"})
