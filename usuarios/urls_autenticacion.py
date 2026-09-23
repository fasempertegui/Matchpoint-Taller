from django.contrib.auth import views
from django.urls import path

from .views_autenticacion import (
    CambioContrasenaView,
    InicioSesionView,
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
]
