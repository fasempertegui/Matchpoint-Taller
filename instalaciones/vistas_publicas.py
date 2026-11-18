from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_GET

from usuarios.models import Rol

from .models import Sede


def exigir_consulta_publica(usuario):
    if not usuario.is_active or not usuario.roles.filter(rol__codigo__in=(Rol.PUBLICO, Rol.ADMINISTRADOR)).exists():
        raise PermissionDenied


@login_required
@require_GET
def sedes_publicas(request):
    exigir_consulta_publica(request.user)
    return render(request, "instalaciones/publico_sedes.html", {"sedes": Sede.objects.filter(estado="activa")})
