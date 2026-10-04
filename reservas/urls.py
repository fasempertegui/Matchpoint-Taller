from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("", views.reserva_lista, name="reserva_lista"),
    path("nueva/", views.reserva_crear, name="reserva_crear"),
    path("<int:pk>/", views.reserva_detalle, name="reserva_detalle"),
    path("sedes/<int:sede_pk>/precios/nuevo/", views.precio_crear, name="precio_crear"),
    path(
        "sedes/<int:sede_pk>/precios/<int:pk>/actualizar/",
        views.precio_actualizar,
        name="precio_actualizar",
    ),
]
