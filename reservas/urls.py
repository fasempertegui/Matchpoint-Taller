from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("sedes/<int:sede_pk>/precios/nuevo/", views.precio_crear, name="precio_crear"),
    path("sedes/<int:sede_pk>/precios/<int:pk>/", views.precio_detalle, name="precio_detalle"),
    path(
        "sedes/<int:sede_pk>/precios/<int:pk>/editar/",
        views.precio_editar,
        name="precio_editar",
    ),
    path(
        "sedes/<int:sede_pk>/precios/<int:pk>/cambiar-estado/",
        views.precio_cambiar_estado,
        name="precio_cambiar_estado",
    ),
]
