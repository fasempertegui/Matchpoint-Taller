from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from usuarios.models import Usuario

from .consultas import listar_contrataciones
from .models import MembresiaUsuario, PlanUsuario


MODELOS_CONTRATACIONES = {"plan": PlanUsuario, "membresia": MembresiaUsuario}


def _exigir_titular(usuario):
    if not usuario.is_authenticated:
        raise PermissionDenied
    return get_object_or_404(
        Usuario, pk=usuario.pk, is_active=True, debe_cambiar_contrasena=False,
    )


def _contexto(tipo):
    url_lista = reverse("membresias:mis_contrataciones") + f"?tipo={tipo}"
    return {
        "propias": True, "tipo": tipo, "plural": "planes" if tipo == "plan" else "membresías",
        "nombre_tipo": "plan" if tipo == "plan" else "membresía",
        "titulo_lista": "Mis contrataciones", "url_lista": url_lista,
        "ruta_detalle": f"membresias:mi_{tipo}_contratado",
        "ruta_comprobante": f"membresias:mi_{tipo}_comprobante",
        "etiqueta_importe": "Importe aplicado (ARS)",
    }


@login_required
@never_cache
@require_GET
def mis_contrataciones(request):
    titular = _exigir_titular(request.user)
    tipo = request.GET.get("tipo", "plan")
    if tipo not in MODELOS_CONTRATACIONES:
        tipo = "plan"
    if not request.GET.get("tipo") and not PlanUsuario.objects.filter(usuario=titular).exists():
        if MembresiaUsuario.objects.filter(usuario=titular).exists():
            tipo = "membresia"
    modelo = MODELOS_CONTRATACIONES[tipo]
    contrataciones = modelo.objects.filter(usuario=titular).select_related("usuario", tipo)
    datos = listar_contrataciones(contrataciones, request.GET, tipo=tipo, buscar_usuario=False)
    return render(request, "membresias/contratacion_lista.html", {**datos, **_contexto(tipo)})


@login_required
@never_cache
@require_GET
def contratacion_propia_detalle(request, pk, tipo="plan"):
    titular = _exigir_titular(request.user)
    modelo = MODELOS_CONTRATACIONES[tipo]
    contratacion = get_object_or_404(
        modelo.objects.filter(usuario=titular).select_related("usuario", tipo), pk=pk,
    )
    return render(request, "membresias/contratacion_detalle.html", {
        **_contexto(tipo), "contratacion": contratacion,
    })


@login_required
@never_cache
@require_GET
def contratacion_propia_comprobante(request, pk, tipo="plan"):
    titular = _exigir_titular(request.user)
    modelo = MODELOS_CONTRATACIONES[tipo]
    contratacion = get_object_or_404(
        modelo.objects.filter(usuario=titular).select_related("usuario", tipo), pk=pk,
    )
    return render(request, "membresias/contratacion_comprobante.html", {
        **_contexto(tipo), "contratacion": contratacion,
    })
