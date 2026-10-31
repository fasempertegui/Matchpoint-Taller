from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .contrataciones import registrar_contratacion_plan
from .fechas import meses_contratables
from .forms import ContratacionPlanForm, SeleccionContratacionPlanForm
from .models import PlanUsuario
from .servicios import exigir_administracion_membresias


def _breadcrumbs(titulo=None):
    items = [
        ("Inicio", reverse("inicio")), ("Membresías", reverse("membresias:catalogos")),
        ("Contrataciones de planes", reverse("membresias:contratacion_plan_lista")),
    ]
    if titulo:
        items.append((titulo, None))
    else:
        items[-1] = (items[-1][0], None)
    return items


@login_required
@never_cache
@require_GET
def contratacion_plan_lista(request):
    exigir_administracion_membresias(request.user)
    contrataciones = PlanUsuario.objects.select_related("usuario", "plan")
    busqueda = request.GET.get("q", "").strip()[:150]
    estado = request.GET.get("estado", "")
    mes = request.GET.get("mes", "")
    meses = meses_contratables()
    if busqueda:
        contrataciones = contrataciones.filter(
            Q(usuario__first_name__icontains=busqueda) | Q(usuario__last_name__icontains=busqueda)
            | Q(usuario__username__icontains=busqueda) | Q(plan__nombre__icontains=busqueda),
        )
    if estado in PlanUsuario.Estado.values:
        contrataciones = contrataciones.filter(estado=estado)
    else:
        estado = ""
    if mes in {fecha.isoformat() for fecha in meses}:
        contrataciones = contrataciones.filter(mes_cubierto=mes)
    else:
        mes = ""
    return render(request, "membresias/contratacion_plan_lista.html", {
        "pagina": Paginator(contrataciones, 25).get_page(request.GET.get("pagina")),
        "busqueda": busqueda, "estado_actual": estado, "mes_actual": mes,
        "estados": PlanUsuario.Estado.choices, "meses": meses,
        "hay_contrataciones": PlanUsuario.objects.exists(), "breadcrumbs": _breadcrumbs(),
    })


@login_required
@never_cache
@require_GET
def contratacion_plan_detalle(request, pk):
    exigir_administracion_membresias(request.user)
    contratacion = get_object_or_404(
        PlanUsuario.objects.select_related("usuario", "plan", "registrado_por", "anulado_por"), pk=pk,
    )
    return render(request, "membresias/contratacion_plan_detalle.html", {
        "contratacion": contratacion, "breadcrumbs": _breadcrumbs(f"Contratación #{contratacion.pk}"),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def contratacion_plan_crear(request):
    exigir_administracion_membresias(request.user)
    datos = request.POST if request.method == "POST" else request.GET
    seleccion = SeleccionContratacionPlanForm(datos if datos else None)
    preparar = request.method == "POST" or datos.get("paso") == "preparar"
    contexto = {
        "titulo": "Registrar contratación de plan", "formulario": seleccion,
        "texto_boton": "Continuar", "metodo_formulario": "get",
        "url_cancelar": reverse("membresias:contratacion_plan_lista"),
        "breadcrumbs": _breadcrumbs("Nueva contratación"),
    }
    if preparar and seleccion.is_valid():
        titular = seleccion.cleaned_data["usuario"]
        plan = seleccion.cleaned_data["plan"]
        formulario = ContratacionPlanForm(
            request.POST if request.method == "POST" else None,
            initial={
                "usuario": titular.pk, "plan": plan.pk, "mes_cubierto": timezone.localdate().replace(day=1),
                "fecha_alta": timezone.localdate(), "precio_aplicado": plan.precio_vigente,
            },
        )
        if request.method == "POST" and formulario.is_valid():
            try:
                contratacion = registrar_contratacion_plan(
                    request.user, usuario_id=formulario.cleaned_data["usuario"],
                    plan_id=formulario.cleaned_data["plan"], mes_cubierto=formulario.cleaned_data["mes_cubierto"],
                    fecha_alta=formulario.cleaned_data["fecha_alta"],
                    precio_aplicado=formulario.cleaned_data["precio_aplicado"],
                    observaciones=formulario.cleaned_data["observaciones"],
                )
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "La contratación del plan fue registrada.")
                return redirect("membresias:contratacion_plan_detalle", pk=contratacion.pk)
        contexto.update({
            "formulario": formulario, "titular": titular, "plan": plan, "texto_boton": "Registrar contratación",
            "metodo_formulario": "post", "precio_propuesto": plan.precio_vigente,
        })
    return render(request, "membresias/contratacion_plan_formulario.html", contexto)
