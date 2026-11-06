from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from instalaciones.models import Sede
from usuarios.models import Rol, Usuario

from .models import Plan


def _exigir_acceso_oferta(usuario):
    if not usuario.is_authenticated or not Usuario.objects.filter(
        pk=usuario.pk, is_active=True, debe_cambiar_contrasena=False,
        roles__rol__codigo__in=(Rol.PUBLICO, Rol.ADMINISTRADOR),
    ).exists():
        raise PermissionDenied


@login_required
@never_cache
@require_GET
def oferta(request):
    _exigir_acceso_oferta(request.user)
    return render(request, "membresias/oferta.html")


def _lista_productos(request, modelo, tipo):
    _exigir_acceso_oferta(request.user)
    productos = modelo.objects.filter(estado=modelo.Estado.ACTIVO)
    busqueda = request.GET.get("q", "").strip()[:150]
    if busqueda:
        productos = productos.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
    return render(request, "membresias/oferta_lista.html", {
        "tipo": tipo, "titulo": "Planes de clases",
        "pagina": Paginator(productos, 25).get_page(request.GET.get("pagina")),
        "busqueda": busqueda,
    })


@login_required
@never_cache
@require_GET
def oferta_planes(request):
    return _lista_productos(request, Plan, "plan")


@login_required
@never_cache
@require_GET
def oferta_tarifas(request):
    _exigir_acceso_oferta(request.user)
    sedes = Sede.objects.filter(estado=Sede.Estado.ACTIVA, precio_reserva_vigente__isnull=False)
    return render(request, "membresias/oferta_tarifas.html", {
        "sedes": sedes,
    })
