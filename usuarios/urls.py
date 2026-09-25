from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("", views.usuario_lista, name="usuario_lista"),
    path("nuevo/", views.usuario_crear, name="usuario_crear"),
    path(
        "nuevo/sugerir-usuario/",
        views.usuario_sugerir_nombre,
        name="usuario_sugerir_nombre",
    ),
    path(
        "nuevo/sugerir-contrasena/",
        views.usuario_sugerir_contrasena,
        name="usuario_sugerir_contrasena",
    ),
    path("<int:pk>/", views.usuario_detalle, name="usuario_detalle"),
    path("<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path(
        "<int:pk>/restablecer-contrasena/",
        views.usuario_restablecer_contrasena,
        name="usuario_restablecer_contrasena",
    ),
    path(
        "<int:pk>/cambiar-estado/",
        views.usuario_cambiar_estado,
        name="usuario_cambiar_estado",
    ),
    path("<int:pk>/roles/<str:rol>/", views.usuario_rol_toggle, name="usuario_rol_toggle"),
]
