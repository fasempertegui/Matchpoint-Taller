from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("precios/", views.precio_lista, name="precio_lista"),
    path("precios/nuevo/", views.precio_crear, name="precio_crear"),
    path("precios/<int:pk>/", views.precio_detalle, name="precio_detalle"),
    path("precios/<int:pk>/editar/", views.precio_editar, name="precio_editar"),
    path(
        "precios/<int:pk>/cambiar-estado/",
        views.precio_cambiar_estado,
        name="precio_cambiar_estado",
    ),
]
