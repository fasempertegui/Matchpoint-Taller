from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import FormView

from .forms import CambioContrasenaForm, InicioSesionForm, UsuarioRegistroForm


class RegistroView(FormView):
    template_name = "usuarios/registro_formulario.html"
    form_class = UsuarioRegistroForm
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.guardar()
        messages.success(self.request, "Tu cuenta fue creada. Ya podés iniciar sesión.")
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
    form_class = CambioContrasenaForm
    success_url = reverse_lazy("password_change_done")

    @transaction.atomic
    def form_valid(self, form):
        respuesta = super().form_valid(form)
        self.request.user.debe_cambiar_contrasena = False
        self.request.user.save(
            update_fields=("debe_cambiar_contrasena", "actualizado_en")
        )
        return respuesta
