from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from usuarios.models import Rol

from .models import Cancha, Sede


def exigir_consulta_publica(usuario):
    if not usuario.is_active or not usuario.roles.filter(rol__codigo__in=(Rol.PUBLICO, Rol.ADMINISTRADOR)).exists():
        raise PermissionDenied


@login_required
@require_GET
def sedes_publicas(request):
    exigir_consulta_publica(request.user)
    return render(request, "instalaciones/publico_sedes.html", {"sedes": Sede.objects.filter(estado="activa")})


@login_required
@require_GET
def sede_publica(request, pk):
    exigir_consulta_publica(request.user)
    sede = get_object_or_404(Sede, pk=pk, estado="activa")
    return render(request, "instalaciones/publico_sede.html", {"sede": sede, "canchas": sede.canchas.filter(estado="activa")})


@login_required
@require_GET
def cancha_publica(request, pk):
    exigir_consulta_publica(request.user)
    cancha = get_object_or_404(Cancha.objects.select_related("sede"), pk=pk, estado="activa", sede__estado="activa")
    return render(request, "instalaciones/publico_cancha.html", {"cancha": cancha})
