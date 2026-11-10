from django.contrib.auth import views
from django.urls import path

from . import vistas_verificacion

from .views_autenticacion import (
    CambioContrasenaView,
    CambioContrasenaCompletadoView,
    InicioSesionView,
    RegistroView,
    nombre_usuario_disponible,
)

urlpatterns = [
    path("verificacion/", vistas_verificacion.estado_verificacion, name="estado_verificacion"),
    path("verificar/", vistas_verificacion.confirmar_verificacion, name="confirmar_verificacion"),
    path("verificacion/reenviar/", vistas_verificacion.solicitar_verificacion, name="solicitar_verificacion"),
    path("verificacion/corregir/", vistas_verificacion.corregir_correo, name="corregir_correo"),
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
