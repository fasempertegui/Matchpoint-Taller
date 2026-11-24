from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from common.modales import es_peticion_modal, respuesta_modal_exito, respuesta_modal_html
from usuarios.models import Rol
from usuarios.acceso import exigir_acceso_operativo

from .continuidad import MODELOS_CONTINUIDAD, contexto_continuidad, responder_continuidad
from .fechas import mes_siguiente
from .forms import ConsultaContinuidadForm, RespuestaContinuidadForm
from .servicios import exigir_administracion_membresias


def _destino_seguro(request, url_defecto):
    siguiente = (request.POST.get("siguiente") or request.GET.get("siguiente") or "").strip()
    if siguiente and url_has_allowed_host_and_scheme(
        siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return siguiente
    return url_defecto


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def responder(request, pk, tipo="plan"):
    titular = exigir_acceso_operativo(request.user)
    if titular.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    contratacion = get_object_or_404(
        MODELOS_CONTINUIDAD[tipo].objects.select_related(tipo, "usuario"), pk=pk, usuario=titular,
    )
    url_detalle = reverse(f"membresias:mi_{tipo}_contratado", args=[pk])
    destino = _destino_seguro(request, url_detalle)
    if not es_peticion_modal(request):
        return redirect(destino)
    contexto = contexto_continuidad(contratacion, titular, tipo=tipo)
    if not contexto["continuidad"]["puede_responder"]:
        messages.info(request, "La encuesta está disponible sólo para consulta.")
        return respuesta_modal_exito(destino)
    formulario = RespuestaContinuidadForm(
        request.POST if request.method == "POST" else None,
        initial={"respuesta": contratacion.respuesta_continuidad},
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            responder_continuidad(titular, pk, formulario.cleaned_data["respuesta"], tipo=tipo)
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Tu respuesta de continuidad fue guardada.")
            return respuesta_modal_exito(destino)
    return respuesta_modal_html(
        request,
        "membresias/_modal_continuidad.html",
        {
            **contexto,
            "contratacion": contratacion,
            "formulario": formulario,
            "accion_url": reverse(f"membresias:mi_{tipo}_continuidad", args=[pk]),
            "nombre_tipo": "membresía" if tipo == "membresia" else "plan",
            "siguiente": destino if destino != url_detalle else "",
        },
        status=400 if formulario.errors else 200,
        amplio=True,
        errores=bool(formulario.errors),
    )


@login_required
@never_cache
@require_GET
def lista(request):
    exigir_administracion_membresias(request.user)
    parametros = request.GET.copy()
    parametros.setdefault("mes", timezone.localdate().replace(day=1).isoformat())
    parametros.setdefault("tipo", "plan")
    formulario = ConsultaContinuidadForm(parametros)
    contexto = {"formulario": formulario}
    if formulario.is_valid():
        tipo = formulario.cleaned_data["tipo"]
        mes = formulario.cleaned_data["mes"]
        respuesta = formulario.cleaned_data["respuesta"]
        contrataciones = MODELOS_CONTINUIDAD[tipo].objects.filter(mes_cubierto=mes).select_related("usuario", tipo)
        if respuesta:
            contrataciones = contrataciones.filter(respuesta_continuidad="" if respuesta == "sin_responder" else respuesta)
        consulta = parametros.copy()
        consulta.pop("pagina", None)
        contexto.update({
            "pagina": Paginator(contrataciones.order_by("usuario__last_name", "usuario__first_name", "pk"), 25).get_page(request.GET.get("pagina")),
            "ruta_detalle": f"membresias:contratacion_{tipo}_detalle", "mes": mes,
            "mes_consultado": mes_siguiente(mes), "consulta": consulta.urlencode(),
        })
    return render(request, "membresias/continuidad_lista.html", contexto)
