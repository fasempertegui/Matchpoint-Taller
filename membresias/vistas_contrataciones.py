from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .contrataciones import (
    anular_contratacion_pase, anular_contratacion_plan, registrar_contratacion_pase,
    registrar_contratacion_plan, version_anulacion_contratacion,
)
from .consultas import listar_contrataciones
from .forms import (
    AnulacionContratacionForm, ContratacionPaseForm, ContratacionPlanForm,
    SeleccionContratacionPaseForm, SeleccionContratacionPlanForm,
)
from .models import PaseUsuario, PlanUsuario
from .servicios import exigir_administracion_membresias


CONFIGURACION_CONTRATACIONES = {
    "plan": {
        "modelo": PlanUsuario, "plural": "planes", "seleccion": SeleccionContratacionPlanForm,
        "formulario": ContratacionPlanForm, "registrar": registrar_contratacion_plan,
        "anular": anular_contratacion_plan,
        "etiqueta_importe": "Importe acordado (ARS)",
    },
    "pase": {
        "modelo": PaseUsuario, "plural": "pases", "seleccion": SeleccionContratacionPaseForm,
        "formulario": ContratacionPaseForm, "registrar": registrar_contratacion_pase,
        "anular": anular_contratacion_pase,
        "etiqueta_importe": "Importe aplicado (ARS)",
    },
}


def _contexto(tipo):
    configuracion = CONFIGURACION_CONTRATACIONES[tipo]
    plural = configuracion["plural"]
    url_lista = reverse(f"membresias:contratacion_{tipo}_lista")
    return {
        "tipo": tipo, "plural": plural, "titulo_lista": f"Contrataciones de {plural}",
        "url_lista": url_lista,
        "url_crear": reverse(f"membresias:contratacion_{tipo}_crear"),
        "ruta_detalle": f"membresias:contratacion_{tipo}_detalle",
        "ruta_comprobante": f"membresias:contratacion_{tipo}_comprobante",
        "ruta_anular": f"membresias:contratacion_{tipo}_anular",
        "ruta_producto": f"membresias:{tipo}_detalle", "etiqueta_importe": configuracion["etiqueta_importe"],
    }


@login_required
@never_cache
@require_GET
def contratacion_lista(request, tipo="plan"):
    exigir_administracion_membresias(request.user)
    modelo = CONFIGURACION_CONTRATACIONES[tipo]["modelo"]
    contrataciones = modelo.objects.select_related("usuario", tipo)
    return render(request, "membresias/contratacion_lista.html", {
        **_contexto(tipo), **listar_contrataciones(contrataciones, request.GET, tipo=tipo),
    })


@login_required
@never_cache
@require_GET
def contratacion_detalle(request, pk, tipo="plan"):
    exigir_administracion_membresias(request.user)
    modelo = CONFIGURACION_CONTRATACIONES[tipo]["modelo"]
    contratacion = get_object_or_404(
        modelo.objects.select_related("usuario", tipo, "registrado_por", "anulado_por"), pk=pk,
    )
    return render(request, "membresias/contratacion_detalle.html", {
        **_contexto(tipo), "contratacion": contratacion,
    })


@login_required
@never_cache
@require_GET
def contratacion_comprobante(request, pk, tipo="plan"):
    exigir_administracion_membresias(request.user)
    modelo = CONFIGURACION_CONTRATACIONES[tipo]["modelo"]
    contratacion = get_object_or_404(
        modelo.objects.select_related("usuario", tipo, "registrado_por", "anulado_por"), pk=pk,
    )
    return render(request, "membresias/contratacion_comprobante.html", {
        **_contexto(tipo), "contratacion": contratacion,
    })


@login_required
@never_cache
@require_GET
def buscar_usuarios_contratacion(request, tipo="plan"):
    exigir_administracion_membresias(request.user)
    busqueda = request.GET.get("q", "").strip()[:100]
    if len(busqueda) < 2:
        return JsonResponse({"resultados": [], "hay_mas": False})
    personas = CONFIGURACION_CONTRATACIONES[tipo]["seleccion"]().fields["usuario"].queryset
    for termino in busqueda.split():
        personas = personas.filter(
            Q(first_name__icontains=termino) | Q(last_name__icontains=termino)
            | Q(username__icontains=termino)
        )
    filas = list(personas.order_by("first_name", "last_name", "username", "pk")[:11])
    return JsonResponse({
        "resultados": [
            {"id": persona.pk, "nombre": str(persona), "usuario": persona.username}
            for persona in filas[:10]
        ],
        "hay_mas": len(filas) > 10,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def contratacion_crear(request, tipo="plan"):
    exigir_administracion_membresias(request.user)
    configuracion = CONFIGURACION_CONTRATACIONES[tipo]
    datos = request.POST if request.method == "POST" else request.GET
    seleccion = configuracion["seleccion"](datos if datos else None)
    paso = datos.get("paso", "")
    confirmar = request.method == "POST" and paso == "confirmar"
    campos_borrador = ("mes_cubierto", "fecha_alta", "precio_aplicado", "observaciones", "producto_precio")
    borrador = {campo: datos[campo] for campo in campos_borrador if campo in datos}
    contexto = {
        **_contexto(tipo),
        "titulo": f"Registrar contratación de {tipo}", "formulario": seleccion,
        "texto_boton": "Continuar", "metodo_formulario": "post",
        "borrador": borrador,
        "url_cancelar": reverse(f"membresias:contratacion_{tipo}_lista"),
    }
    valor_usuario = seleccion["usuario"].value()
    if valor_usuario and str(valor_usuario).isascii() and str(valor_usuario).isdigit():
        contexto["usuario_seleccionado"] = seleccion.fields["usuario"].queryset.filter(pk=valor_usuario).first()
    contexto["url_buscar_usuarios"] = reverse(f"membresias:contratacion_{tipo}_buscar_usuarios")
    if paso in ("preparar", "confirmar") and seleccion.is_valid():
        titular = seleccion.cleaned_data["usuario"]
        producto = seleccion.cleaned_data[tipo]
        iniciales = {
            "mes_cubierto": timezone.localdate().replace(day=1), "fecha_alta": timezone.localdate(),
            **{campo: valor for campo, valor in borrador.items() if campo != "producto_precio"},
            "usuario": titular.pk, tipo: producto.pk,
        }
        if tipo == "pase" or borrador.get("producto_precio") != str(producto.pk):
            iniciales["precio_aplicado"] = producto.precio_vigente
        formulario = configuracion["formulario"](
            request.POST if confirmar else None, initial=iniciales,
        )
        if confirmar and formulario.is_valid():
            argumentos = {
                "usuario_id": formulario.cleaned_data["usuario"], f"{tipo}_id": formulario.cleaned_data[tipo],
                "mes_cubierto": formulario.cleaned_data["mes_cubierto"],
                "fecha_alta": formulario.cleaned_data["fecha_alta"],
                "precio_aplicado": formulario.cleaned_data["precio_aplicado"],
                "observaciones": formulario.cleaned_data["observaciones"],
            }
            try:
                contratacion = configuracion["registrar"](request.user, **argumentos)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, f"La contratación del {tipo} fue registrada.")
                return redirect(f"membresias:contratacion_{tipo}_detalle", pk=contratacion.pk)
        contexto.update({
            "formulario": formulario, "titular": titular, "producto": producto,
            "texto_boton": "Registrar contratación", "metodo_formulario": "post",
            "precio_propuesto": producto.precio_vigente,
        })
    return render(request, "membresias/contratacion_formulario.html", contexto)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def contratacion_anular(request, pk, tipo="plan"):
    actor = exigir_administracion_membresias(request.user)
    configuracion = CONFIGURACION_CONTRATACIONES[tipo]
    modelo = configuracion["modelo"]
    contratacion = get_object_or_404(modelo.objects.select_related("usuario", tipo), pk=pk)
    url_detalle = reverse(f"membresias:contratacion_{tipo}_detalle", args=[pk])
    if contratacion.estado != modelo.Estado.ACTIVO:
        if contratacion.estado == modelo.Estado.ANULADO:
            messages.info(request, "La contratación ya está Anulada.")
        else:
            messages.error(request, "Sólo se pueden anular contrataciones Activas.")
        return redirect(url_detalle)
    formulario = AnulacionContratacionForm(
        request.POST if request.method == "POST" else None,
        initial={"version": version_anulacion_contratacion(actor, contratacion, tipo=tipo)},
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            configuracion["anular"](actor, pk, **formulario.cleaned_data)
        except ValidationError as error:
            contratacion.refresh_from_db()
            if contratacion.estado != modelo.Estado.ACTIVO:
                for mensaje in error.messages:
                    messages.error(request, mensaje)
                return redirect(url_detalle)
            formulario.add_error(None, error)
        else:
            messages.success(request, f"La contratación del {tipo} está Anulada.")
            return redirect(url_detalle)
    return render(request, "membresias/contratacion_anular.html", {
        **_contexto(tipo), "contratacion": contratacion,
        "titulo": f"Anular contratación de {tipo}", "formulario": formulario,
        "texto_boton": "Confirmar anulación", "url_cancelar": url_detalle,
    })
