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

from .contrataciones import registrar_contratacion_pase, registrar_contratacion_plan
from .fechas import meses_contratables
from .forms import (
    ContratacionPaseForm, ContratacionPlanForm, SeleccionContratacionPaseForm, SeleccionContratacionPlanForm,
)
from .models import PaseUsuario, PlanUsuario
from .servicios import exigir_administracion_membresias


CONFIGURACION_CONTRATACIONES = {
    "plan": {
        "modelo": PlanUsuario, "plural": "planes", "seleccion": SeleccionContratacionPlanForm,
        "formulario": ContratacionPlanForm, "registrar": registrar_contratacion_plan,
        "etiqueta_importe": "Importe acordado (ARS)",
    },
    "pase": {
        "modelo": PaseUsuario, "plural": "pases", "seleccion": SeleccionContratacionPaseForm,
        "formulario": ContratacionPaseForm, "registrar": registrar_contratacion_pase,
        "etiqueta_importe": "Importe aplicado (ARS)",
    },
}


def _contexto(tipo, titulo=None):
    configuracion = CONFIGURACION_CONTRATACIONES[tipo]
    plural = configuracion["plural"]
    url_lista = reverse(f"membresias:contratacion_{tipo}_lista")
    breadcrumbs = [
        ("Inicio", reverse("inicio")), ("Membresías", reverse("membresias:catalogos")),
        (f"Contrataciones de {plural}", url_lista),
    ]
    if titulo:
        breadcrumbs.append((titulo, None))
    else:
        breadcrumbs[-1] = (breadcrumbs[-1][0], None)
    return {
        "tipo": tipo, "plural": plural, "breadcrumbs": breadcrumbs, "url_lista": url_lista,
        "url_crear": reverse(f"membresias:contratacion_{tipo}_crear"),
        "ruta_detalle": f"membresias:contratacion_{tipo}_detalle",
        "ruta_producto": f"membresias:{tipo}_detalle", "etiqueta_importe": configuracion["etiqueta_importe"],
    }


@login_required
@never_cache
@require_GET
def contratacion_lista(request, tipo="plan"):
    exigir_administracion_membresias(request.user)
    modelo = CONFIGURACION_CONTRATACIONES[tipo]["modelo"]
    contrataciones = modelo.objects.select_related("usuario", tipo)
    busqueda = request.GET.get("q", "").strip()[:150]
    estado = request.GET.get("estado", "")
    mes = request.GET.get("mes", "")
    meses = meses_contratables()
    if busqueda:
        contrataciones = contrataciones.filter(
            Q(usuario__first_name__icontains=busqueda) | Q(usuario__last_name__icontains=busqueda)
            | Q(usuario__username__icontains=busqueda) | Q(**{f"{tipo}__nombre__icontains": busqueda}),
        )
    if estado in modelo.Estado.values:
        contrataciones = contrataciones.filter(estado=estado)
    else:
        estado = ""
    if mes in {fecha.isoformat() for fecha in meses}:
        contrataciones = contrataciones.filter(mes_cubierto=mes)
    else:
        mes = ""
    return render(request, "membresias/contratacion_lista.html", {
        **_contexto(tipo), "pagina": Paginator(contrataciones, 25).get_page(request.GET.get("pagina")),
        "busqueda": busqueda, "estado_actual": estado, "mes_actual": mes,
        "estados": modelo.Estado.choices, "meses": meses, "hay_contrataciones": modelo.objects.exists(),
    })


@login_required
@never_cache
@require_GET
def contratacion_detalle(request, pk, tipo="plan"):
    exigir_administracion_membresias(request.user)
    modelo = CONFIGURACION_CONTRATACIONES[tipo]["modelo"]
    contratacion = get_object_or_404(
        modelo.objects.select_related("usuario", tipo, "registrado_por", "anulado_por"), pk=pk,
    )
    return render(request, "membresias/contratacion_detalle.html", {
        **_contexto(tipo, f"Contratación #{contratacion.pk}"), "contratacion": contratacion,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def contratacion_crear(request, tipo="plan"):
    exigir_administracion_membresias(request.user)
    configuracion = CONFIGURACION_CONTRATACIONES[tipo]
    datos = request.POST if request.method == "POST" else request.GET
    seleccion = configuracion["seleccion"](datos if datos else None)
    preparar = request.method == "POST" or datos.get("paso") == "preparar"
    contexto = {
        **_contexto(tipo, "Nueva contratación"),
        "titulo": f"Registrar contratación de {tipo}", "formulario": seleccion,
        "texto_boton": "Continuar", "metodo_formulario": "get",
        "url_cancelar": reverse(f"membresias:contratacion_{tipo}_lista"),
    }
    if preparar and seleccion.is_valid():
        titular = seleccion.cleaned_data["usuario"]
        producto = seleccion.cleaned_data[tipo]
        formulario = configuracion["formulario"](
            request.POST if request.method == "POST" else None,
            initial={
                "usuario": titular.pk, tipo: producto.pk, "mes_cubierto": timezone.localdate().replace(day=1),
                "fecha_alta": timezone.localdate(), "precio_aplicado": producto.precio_vigente,
            },
        )
        if request.method == "POST" and formulario.is_valid():
            argumentos = {
                "usuario_id": formulario.cleaned_data["usuario"], f"{tipo}_id": formulario.cleaned_data[tipo],
                "mes_cubierto": formulario.cleaned_data["mes_cubierto"],
                "fecha_alta": formulario.cleaned_data["fecha_alta"],
                "precio_aplicado": formulario.cleaned_data["precio_aplicado"],
                "observaciones": formulario.cleaned_data["observaciones"],
            }
            try:
                contratacion = configuracion["registrar"](request.user, **argumentos)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, f"La contratación del {tipo} fue registrada.")
                return redirect(f"membresias:contratacion_{tipo}_detalle", pk=contratacion.pk)
        contexto.update({
            "formulario": formulario, "titular": titular, "producto": producto,
            "texto_boton": "Registrar contratación", "metodo_formulario": "post",
            "precio_propuesto": producto.precio_vigente,
        })
    return render(request, "membresias/contratacion_formulario.html", contexto)
