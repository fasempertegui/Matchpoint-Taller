from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import PlanForm
from .models import Plan
from .servicios import cambiar_estado_plan, exigir_administracion_membresias, guardar_plan, version_plan


def _breadcrumbs(plan=None, titulo=None):
    items = [("Inicio", reverse("inicio")), ("Planes", reverse("membresias:plan_lista"))]
    if plan is not None:
        items.append((plan.nombre, reverse("membresias:plan_detalle", args=[plan.pk])))
    if titulo:
        items.append((titulo, None))
    else:
        items[-1] = (items[-1][0], None)
    return items


@login_required
@never_cache
@require_GET
def plan_lista(request):
    exigir_administracion_membresias(request.user)
    planes = Plan.objects.all()
    busqueda = request.GET.get("q", "").strip()[:150]
    estado = request.GET.get("estado", "")
    if busqueda:
        planes = planes.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
    if estado in Plan.Estado.values:
        planes = planes.filter(estado=estado)
    else:
        estado = ""
    return render(request, "membresias/plan_lista.html", {
        "pagina": Paginator(planes, 25).get_page(request.GET.get("pagina")),
        "busqueda": busqueda, "estado_actual": estado, "estados": Plan.Estado.choices,
        "hay_planes": Plan.objects.exists(), "breadcrumbs": _breadcrumbs(),
    })


@login_required
@never_cache
@require_GET
def plan_detalle(request, pk):
    usuario = exigir_administracion_membresias(request.user)
    plan = get_object_or_404(Plan, pk=pk)
    return render(request, "membresias/plan_detalle.html", {
        "plan": plan, "version": version_plan(usuario, plan), "breadcrumbs": _breadcrumbs(plan),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def plan_formulario(request, pk=None):
    usuario = exigir_administracion_membresias(request.user)
    plan = get_object_or_404(Plan, pk=pk) if pk is not None else None
    titulo = "Editar plan" if plan is not None else "Nuevo plan"
    formulario = PlanForm(
        request.POST if request.method == "POST" else None, instance=plan,
        initial={"version": version_plan(usuario, plan)} if plan is not None else None,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            guardado = guardar_plan(usuario, plan_id=pk, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "El plan fue guardado.")
            return redirect("membresias:plan_detalle", pk=guardado.pk)
    return render(request, "membresias/plan_formulario.html", {
        "formulario": formulario, "titulo": titulo, "breadcrumbs": _breadcrumbs(plan, titulo),
        "url_cancelar": reverse("membresias:plan_detalle", args=[pk]) if pk is not None
            else reverse("membresias:plan_lista"),
    })


@login_required
@never_cache
@require_POST
def plan_cambiar_estado(request, pk):
    exigir_administracion_membresias(request.user)
    get_object_or_404(Plan, pk=pk)
    try:
        plan = cambiar_estado_plan(
            request.user, pk, request.POST.get("estado"), version=request.POST.get("version", ""),
        )
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, f"El plan está {plan.get_estado_display().lower()}.")
    return redirect("membresias:plan_detalle", pk=pk)
