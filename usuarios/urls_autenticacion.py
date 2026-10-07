from django.contrib.auth import views
from django.urls import path

from .views_autenticacion import (
    CambioContrasenaView,
    CambioContrasenaCompletadoView,
    InicioSesionView,
    RegistroView,
    nombre_usuario_disponible,
)

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("nombre-usuario/", nombre_usuario_disponible, name="nombre_usuario_disponible"),
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
        CambioContrasenaCompletadoView.as_view(),
        name="password_change_done",
    ),
]
