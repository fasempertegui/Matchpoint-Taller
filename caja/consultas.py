from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse

from usuarios.models import Rol

from .finanzas import resumen_financiero
from .ingresos import ORIGENES
from .models import MovimientoFondo, RevisionDiferenciaCaja, SesionCaja


def anotar_revision_diferencias(consulta):
    rev_apertura = RevisionDiferenciaCaja.objects.filter(
        sesion_id=OuterRef("pk"), momento=RevisionDiferenciaCaja.Momento.APERTURA,
    )
    rev_cierre = RevisionDiferenciaCaja.objects.filter(
        sesion_id=OuterRef("pk"), momento=RevisionDiferenciaCaja.Momento.CIERRE,
    )
    return consulta.annotate(_rev_apertura=Exists(rev_apertura), _rev_cierre=Exists(rev_cierre))


def filtrar_sesiones_por_revision(consulta, estado_revision):
    tiene_dif_apertura = Q(diferencia_apertura__isnull=False) & ~Q(diferencia_apertura=0)
    tiene_dif_cierre = Q(diferencia__isnull=False) & ~Q(diferencia=0)
    if estado_revision == "sin_diferencias":
        return consulta.exclude(tiene_dif_apertura | tiene_dif_cierre)
    consulta = anotar_revision_diferencias(consulta)
    pendiente = (tiene_dif_apertura & Q(_rev_apertura=False)) | (tiene_dif_cierre & Q(_rev_cierre=False))
    if estado_revision == "pendiente":
        return consulta.filter(pendiente)
    if estado_revision == "revisada":
        return consulta.filter(tiene_dif_apertura | tiene_dif_cierre).exclude(pendiente)
    return consulta


def sesiones_con_diferencia_pendiente_queryset():
    return filtrar_sesiones_por_revision(SesionCaja.objects.all(), "pendiente")


def contexto_financiero(actor, tipo, origen, parametros):
    if not actor.is_authenticated or not actor.esta_habilitado or actor.debe_cambiar_contrasena:
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
    filtros.pop("pagina_importes", None)
    ajustes = origen.ajustes_importe.select_related("registrado_por")
    pagina_importes = Paginator(ajustes, 25).get_page(parametros.get("pagina_importes"))
    acciones = {"url_cobrar": None, "url_devolver": None, "url_excedente": None, "url_ajustar_importe": None}
    if administrador:
        if resumen["maximo_ingreso"] > 0:
            acciones["url_ajustar_importe"] = reverse("caja:ajustar_importe", args=[tipo, origen.pk])
        sesion = SesionCaja.objects.filter(estado="abierta", responsable=actor).first()
        if sesion:
            consulta = "?" + urlencode({"tipo": tipo, "origen": origen.pk})
            if resumen["maximo_ingreso"] > 0:
                acciones["url_cobrar"] = reverse("caja:ingreso_crear", args=[sesion.pk]) + consulta
            if resumen["maximo_devolucion"] > 0:
                acciones["url_devolver"] = reverse("caja:devolucion_crear", args=[sesion.pk]) + consulta
            if resumen["maximo_ingreso"] > 0:
                acciones["url_excedente"] = reverse("caja:ingreso_excedente", args=[sesion.pk, tipo, origen.pk])
    return {
        "finanzas": resumen, "pagina_finanzas": pagina, "parametros_finanzas": filtros.urlencode(),
        "historial_financiero_abierto": "pagina_finanzas" in parametros or "pagina_importes" in parametros,
        "pagina_importes": pagina_importes, "historial_importes_abierto": "pagina_importes" in parametros,
        "finanzas_administrativas": administrador, **acciones,
    }
