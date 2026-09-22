from django.urls import path

from . import views

app_name = "instalaciones"

urlpatterns = [
    path("", views.sede_lista, name="sede_lista"),
    path("nueva/", views.sede_crear, name="sede_crear"),
    path("<int:pk>/", views.sede_detalle, name="sede_detalle"),
    path("<int:pk>/editar/", views.sede_editar, name="sede_editar"),
    path("<int:pk>/cambiar-estado/", views.sede_cambiar_estado, name="sede_cambiar_estado"),
    path("<int:sede_pk>/canchas/nueva/", views.cancha_crear, name="cancha_crear"),
    path("<int:sede_pk>/canchas/<int:pk>/editar/", views.cancha_editar, name="cancha_editar"),
    path(
        "<int:sede_pk>/canchas/<int:pk>/cambiar-estado/",
        views.cancha_cambiar_estado,
        name="cancha_cambiar_estado",
    ),
]
