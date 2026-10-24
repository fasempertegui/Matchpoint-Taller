from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("<int:pk>/", views.reserva_detalle, name="reserva_detalle"),
    path("<int:pk>/comprobante/", views.reserva_comprobante, name="reserva_comprobante"),
    path("<int:pk>/anular/", views.reserva_anular, name="reserva_anular"),
    path("<int:pk>/finalizar/", views.reserva_finalizar, name="reserva_finalizar"),
]
