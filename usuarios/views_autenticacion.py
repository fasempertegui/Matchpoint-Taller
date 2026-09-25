from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import FormView
from django.views.decorators.http import require_GET

from .forms import InicioSesionForm, UsuarioRegistroForm, generar_nombre_usuario


@require_GET
def nombre_usuario_disponible(request):
    nombre = request.GET.get("nombre", "").strip()
    apellido = request.GET.get("apellido", "").strip()
    if not nombre or not apellido:
        return JsonResponse(
            {"error": "Ingresá el nombre y el apellido para generar el usuario."},
            status=400,
        )
    try:
        nombre_usuario = generar_nombre_usuario(nombre, apellido)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)
    return JsonResponse({"nombre_usuario": nombre_usuario})


class RegistroView(FormView):
    template_name = "usuarios/registro_formulario.html"
    form_class = UsuarioRegistroForm
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        usuario = form.guardar()
        messages.success(
            self.request,
            f"Tu cuenta fue creada. Tu nombre de usuario es {usuario.username}. Ya podés iniciar sesión.",
        )
        return super().form_valid(form)


class InicioSesionView(auth_views.LoginView):
    template_name = "autenticacion/iniciar_sesion.html"
    authentication_form = InicioSesionForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.debe_cambiar_contrasena:
            return reverse("password_change")
        return super().get_success_url()


class CambioContrasenaView(auth_views.PasswordChangeView):
    template_name = "autenticacion/cambio_contrasena_formulario.html"
    success_url = reverse_lazy("password_change_done")

    @transaction.atomic
    def form_valid(self, form):
        respuesta = super().form_valid(form)
        self.request.user.debe_cambiar_contrasena = False
        self.request.user.save(
            update_fields=("debe_cambiar_contrasena", "actualizado_en")
        )
        return respuesta
