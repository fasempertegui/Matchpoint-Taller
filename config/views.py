from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from usuarios.models import Rol


@login_required
def inicio(request):
    plantilla = (
        "inicio_administracion.html"
        if request.user.tiene_rol(Rol.ADMINISTRADOR)
        else "inicio_portal.html"
    )
    return render(request, plantilla)
