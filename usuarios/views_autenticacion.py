from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import FormView
from django.views.decorators.http import require_GET

from auditoria.contexto import contexto_auditoria
from auditoria.models import LogAuditoria

from .forms import CambioContrasenaForm, InicioSesionForm, UsuarioRegistroForm, generar_nombre_usuario
from .navegacion import breadcrumbs_usuario


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
    extra_context = {
        "breadcrumbs": [("Acceso", None), ("Iniciar sesión", reverse_lazy("login")), ("Crear cuenta", None)],
    }

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
    extra_context = {"breadcrumbs": [("Acceso", None), ("Iniciar sesión", None)]}

    def post(self, request, *args, **kwargs):
        with contexto_auditoria(origen="autenticacion", accion=LogAuditoria.Accion.ACTUALIZACION_HASH):
            return super().post(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.debe_cambiar_contrasena:
            return reverse("password_change")
        return super().get_success_url()


class CambioContrasenaView(auth_views.PasswordChangeView):
    template_name = "autenticacion/cambio_contrasena_formulario.html"
    form_class = CambioContrasenaForm
    success_url = reverse_lazy("password_change_done")

    def post(self, request, *args, **kwargs):
        with contexto_auditoria(request.user, accion=LogAuditoria.Accion.ACTUALIZACION_HASH):
            return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.request.user.debe_cambiar_contrasena:
            contexto["breadcrumbs"] = [("Acceso", None), ("Cambiar contraseña", None)]
        else:
            contexto["breadcrumbs"] = breadcrumbs_usuario(self.request.user, self.request.user) + [("Cambiar contraseña", None)]
        return contexto

    def form_valid(self, form):
        with contexto_auditoria(self.request.user, accion=LogAuditoria.Accion.CAMBIO_CONTRASENA):
            usuario = form.save(commit=False)
            usuario.debe_cambiar_contrasena = False
            usuario.save(update_fields=("password", "debe_cambiar_contrasena", "actualizado_en"))
            update_session_auth_hash(self.request, usuario)
        return redirect(self.get_success_url())


class CambioContrasenaCompletadoView(auth_views.PasswordChangeDoneView):
    template_name = "autenticacion/cambio_contrasena_completado.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["breadcrumbs"] = breadcrumbs_usuario(self.request.user, self.request.user) + [("Contraseña actualizada", None)]
        return contexto
