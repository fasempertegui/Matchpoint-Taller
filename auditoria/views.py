from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from usuarios.models import Rol

from .models import LogAuditoria
from .presentacion import preparar_filas


@login_required
@require_GET
def auditoria_lista(request):
    if (
        not request.user.is_active
        or request.user.debe_cambiar_contrasena
        or not request.user.tiene_rol(Rol.ADMINISTRADOR)
    ):
        raise PermissionDenied
    registros = LogAuditoria.objects.select_related("usuario").all()
    pagina = Paginator(registros, 25).get_page(request.GET.get("pagina"))
    filas = preparar_filas(list(pagina))
    return render(request, "auditoria/auditoria_lista.html", {
        "filas": filas,
        "pagina": pagina,
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Auditoría", None)],
    })
