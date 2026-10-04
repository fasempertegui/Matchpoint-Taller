from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("", views.reserva_lista, name="reserva_lista"),
    path("nueva/", views.reserva_crear, name="reserva_crear"),
    path("<int:pk>/", views.reserva_detalle, name="reserva_detalle"),
    path("<int:pk>/comprobante/", views.reserva_comprobante, name="reserva_comprobante"),
    path("<int:pk>/anular/", views.reserva_anular, name="reserva_anular"),
    path("<int:pk>/finalizar/", views.reserva_finalizar, name="reserva_finalizar"),
    path("sedes/<int:sede_pk>/precios/nuevo/", views.precio_crear, name="precio_crear"),
    path(
        "sedes/<int:sede_pk>/precios/<int:pk>/actualizar/",
        views.precio_actualizar,
        name="precio_actualizar",
    ),
]
