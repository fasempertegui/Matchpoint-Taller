from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("disponibilidad/", views.disponibilidad, name="disponibilidad"),
    path("sedes/<int:sede_pk>/precios/nuevo/", views.precio_crear, name="precio_crear"),
    path(
        "sedes/<int:sede_pk>/precios/<int:pk>/actualizar/",
        views.precio_actualizar,
        name="precio_actualizar",
    ),
]
