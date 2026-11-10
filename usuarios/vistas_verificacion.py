from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import CorregirCorreoForm, ReenvioVerificacionForm
from .verificacion import consultar_verificacion, corregir_correo_inicial, reenviar_verificacion, verificar_correo


@never_cache
@require_GET
def estado_verificacion(request):
    return render(request, "autenticacion/verificacion_estado.html")


@never_cache
@require_http_methods(["GET", "POST"])
def confirmar_verificacion(request):
    token = request.POST.get("token", "") if request.method == "POST" else request.GET.get("token", "")
    resultado = ""
    confirmar = False
    try:
        if request.method == "POST":
            resultado = verificar_correo(token)
        else:
            resultado = consultar_verificacion(token)
            confirmar = not resultado
    except ValidationError as error:
        resultado = error.messages[0]
    return render(request, "autenticacion/verificacion_confirmar.html", {"resultado": resultado, "confirmar": confirmar, "token": token if confirmar else ""})


@never_cache
@require_http_methods(["GET", "POST"])
def solicitar_verificacion(request):
    formulario = ReenvioVerificacionForm(request.POST or None)
    resultado = ""
    if request.method == "POST" and formulario.is_valid():
        resultado = reenviar_verificacion(formulario.cleaned_data["email"])
        formulario = None
    return render(request, "autenticacion/verificacion_reenviar.html", {"formulario": formulario, "resultado": resultado})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def corregir_correo(request):
    if request.user.correo_verificado_en is not None:
        return redirect("estado_verificacion")
    formulario = CorregirCorreoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            corregir_correo_inicial(request.user, **formulario.cleaned_data)
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Enviamos la verificación al correo corregido.")
            return redirect("estado_verificacion")
    return render(request, "autenticacion/verificacion_corregir.html", {"formulario": formulario})


@never_cache
@require_http_methods(["GET", "POST"])
def confirmar_cambio_correo(request):
    from .correo import confirmar_cambio_correo as confirmar, consultar_cambio_correo

    token = request.POST.get("token", "") if request.method == "POST" else request.GET.get("token", "")
    resultado, puede_confirmar = "", False
    try:
        if request.method == "POST":
            confirmar(token)
            resultado = "Tu correo fue actualizado."
        else:
            consultar_cambio_correo(token)
            puede_confirmar = True
    except ValidationError as error:
        resultado = error.messages[0]
    return render(request, "autenticacion/cambio_correo_confirmar.html", {"resultado": resultado, "confirmar": puede_confirmar, "token": token if puede_confirmar else ""})
