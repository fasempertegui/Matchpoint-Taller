from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from instalaciones.models import Sede
from usuarios.models import Rol, Usuario

from .models import Pase, Plan


def _exigir_acceso_oferta(usuario):
    if not usuario.is_authenticated or not Usuario.objects.filter(
        pk=usuario.pk, is_active=True, debe_cambiar_contrasena=False,
        roles__rol__codigo__in=(Rol.PUBLICO, Rol.ADMINISTRADOR),
    ).exists():
        raise PermissionDenied


def _breadcrumbs(tipo=None):
    items = [("Inicio", reverse("inicio")), ("Oferta", reverse("membresias:oferta"))]
    if tipo is not None:
        nombre = "Planes" if tipo == "plan" else "Pases de cancha"
        destino = "membresias:oferta_planes" if tipo == "plan" else "membresias:oferta_pases"
        items.append((nombre, reverse(destino)))
    items[-1] = (items[-1][0], None)
    return items


@login_required
@never_cache
@require_GET
def oferta(request):
    _exigir_acceso_oferta(request.user)
    return render(request, "membresias/oferta.html", {"breadcrumbs": _breadcrumbs()})


def _lista_productos(request, modelo, tipo):
    _exigir_acceso_oferta(request.user)
    productos = modelo.objects.filter(estado=modelo.Estado.ACTIVO)
    busqueda = request.GET.get("q", "").strip()[:150]
    if busqueda:
        productos = productos.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
    return render(request, "membresias/oferta_lista.html", {
        "tipo": tipo, "titulo": "Planes de clases" if tipo == "plan" else "Pases de cancha",
        "pagina": Paginator(productos, 25).get_page(request.GET.get("pagina")),
        "busqueda": busqueda, "breadcrumbs": _breadcrumbs(tipo),
    })


@login_required
@never_cache
@require_GET
def oferta_planes(request):
    return _lista_productos(request, Plan, "plan")


@login_required
@never_cache
@require_GET
def oferta_pases(request):
    return _lista_productos(request, Pase, "pase")


@login_required
@never_cache
@require_GET
def oferta_tarifas(request):
    _exigir_acceso_oferta(request.user)
    sedes = Sede.objects.filter(estado=Sede.Estado.ACTIVA, precio_reserva_vigente__isnull=False)
    return render(request, "membresias/oferta_tarifas.html", {
        "sedes": sedes,
        "breadcrumbs": [
            ("Inicio", reverse("inicio")), ("Oferta", reverse("membresias:oferta")),
            ("Tarifas de reservas", None),
        ],
    })
