from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.urls import reverse

from usuarios.models import Rol

from .ingresos import cobros_del_origen
from .models import SesionCaja


def contexto_cobros(actor, tipo, origen, parametros):
    if not actor.is_authenticated or not actor.is_active or actor.debe_cambiar_contrasena:
        raise PermissionDenied
    administrador = actor.tiene_rol(Rol.ADMINISTRADOR)
    titular_id = origen.organizador_id if tipo == "reserva" else origen.usuario_id
    if not administrador and actor.pk != titular_id:
        raise PermissionDenied
    pagina = Paginator(cobros_del_origen(tipo, origen.pk), 25).get_page(parametros.get("pagina_cobros"))
    filtros = parametros.copy()
    filtros.pop("pagina_cobros", None)
    url_cobrar = None
    anulado = origen.evento.estado == "anulado" if tipo == "reserva" else origen.estado == "anulado"
    if administrador and not anulado:
        sesion = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
        if sesion:
            url_cobrar = reverse("caja:ingreso_crear", args=[sesion.pk]) + "?" + urlencode({"tipo": tipo, "origen": origen.pk})
    return {"pagina_cobros": pagina, "parametros_cobros": filtros.urlencode(), "url_cobrar": url_cobrar, "cobros_administrativos": administrador}
