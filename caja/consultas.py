from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.urls import reverse

from usuarios.models import Rol

from .finanzas import resumen_financiero
from .ingresos import ORIGENES
from .models import MovimientoFondo, SesionCaja


def contexto_financiero(actor, tipo, origen, parametros):
    if not actor.is_authenticated or not actor.is_active or actor.debe_cambiar_contrasena:
        raise PermissionDenied
    administrador = actor.tiene_rol(Rol.ADMINISTRADOR)
    titular_id = origen.organizador_id if tipo == "reserva" else origen.usuario_id
    if not administrador and actor.pk != titular_id:
        raise PermissionDenied
    resumen = resumen_financiero(tipo, origen)
    movimientos = MovimientoFondo.objects.filter(**{ORIGENES[tipo][1]: origen.pk}).order_by("-creado_en", "-pk")
    pagina = Paginator(movimientos, 25).get_page(parametros.get("pagina_finanzas"))
    filtros = parametros.copy()
    filtros.pop("pagina_finanzas", None)
    acciones = {"url_cobrar": None, "url_devolver": None}
    if administrador:
        sesion = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
        if sesion:
            consulta = "?" + urlencode({"tipo": tipo, "origen": origen.pk})
            if not resumen["operacion_anulada"]:
                acciones["url_cobrar"] = reverse("caja:ingreso_crear", args=[sesion.pk]) + consulta
            if resumen["maximo_devolucion"] > 0:
                acciones["url_devolver"] = reverse("caja:devolucion_crear", args=[sesion.pk]) + consulta
    return {
        "finanzas": resumen, "pagina_finanzas": pagina, "parametros_finanzas": filtros.urlencode(),
        "historial_financiero_abierto": "pagina_finanzas" in parametros,
        "finanzas_administrativas": administrador, **acciones,
    }
