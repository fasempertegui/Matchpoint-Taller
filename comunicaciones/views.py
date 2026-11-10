from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from usuarios.models import Rol, Usuario

from .models import EnvioEmail


@login_required
@never_cache
@require_GET
def envios_lista(request):
    if not Usuario.objects.filter(
        pk=request.user.pk, is_active=True, correo_verificado_en__isnull=False, debe_cambiar_contrasena=False,
        roles__rol__codigo=Rol.ADMINISTRADOR,
    ).exists():
        raise PermissionDenied
    registros = EnvioEmail.objects.defer("datos", "reserva_token", "clave")
    estado = request.GET.get("estado", "")
    tipo = request.GET.get("tipo", "")
    busqueda = request.GET.get("q", "").strip()[:150]
    if estado in EnvioEmail.Estado.values:
        registros = registros.filter(estado=estado)
    else:
        estado = ""
    if tipo in EnvioEmail.Tipo.values:
        registros = registros.filter(tipo=tipo)
    else:
        tipo = ""
    if busqueda:
        registros = registros.filter(destinatario__icontains=busqueda)
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "comunicaciones/envios_lista.html", {
        "pagina": Paginator(registros, 25).get_page(request.GET.get("pagina")),
        "estados": EnvioEmail.Estado.choices, "tipos": EnvioEmail.Tipo.choices,
        "estado_actual": estado, "tipo_actual": tipo, "busqueda": busqueda,
        "filtros": filtros.urlencode(), "mostrar_filtros": request.GET.get("filtrar") == "1",
    })
