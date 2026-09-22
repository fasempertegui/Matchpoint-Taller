from django.contrib.auth import views
from django.urls import path

from .views_autenticacion import (
    CambioContrasenaView,
    InicioSesionView,
    RecuperacionContrasenaConfirmacionView,
    RegistroView,
)

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path(
        "login/",
        InicioSesionView.as_view(),
        name="login",
    ),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path(
        "password_change/",
        CambioContrasenaView.as_view(),
        name="password_change",
    ),
    path(
        "password_change/done/",
        views.PasswordChangeDoneView.as_view(
            template_name="autenticacion/cambio_contrasena_completado.html"
        ),
        name="password_change_done",
    ),
    path(
        "password_reset/",
        views.PasswordResetView.as_view(
            template_name="autenticacion/recuperacion_contrasena_formulario.html",
            email_template_name="autenticacion/recuperacion_contrasena_email.html",
            subject_template_name="autenticacion/recuperacion_contrasena_asunto.txt",
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        views.PasswordResetDoneView.as_view(
            template_name="autenticacion/recuperacion_contrasena_enviada.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        RecuperacionContrasenaConfirmacionView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        views.PasswordResetCompleteView.as_view(
            template_name="autenticacion/recuperacion_contrasena_completada.html"
        ),
        name="password_reset_complete",
    ),
]
