from django.urls import path

from . import views, vistas_comerciales

app_name = "reservas"

urlpatterns = [
    path("buscar-invitados/", vistas_comerciales.buscar_invitados, name="buscar_invitados"),
    path("nueva/", vistas_comerciales.crear_reserva, name="crear_reserva"),
    path("mis-reservas/", vistas_comerciales.mis_reservas, name="mis_reservas"),
    path("uso/", vistas_comerciales.uso_membresia, name="uso_membresia"),
    path("<int:pk>/invitados/", vistas_comerciales.reserva_invitados, name="reserva_invitados"),
    path("<int:pk>/socios/", vistas_comerciales.reserva_socios, name="reserva_socios"),
    path("<int:pk>/responder/", vistas_comerciales.reserva_responder, name="reserva_responder"),
    path("<int:pk>/resultado/", vistas_comerciales.reserva_resultado, name="reserva_resultado"),
    path("<int:pk>/", views.reserva_detalle, name="reserva_detalle"),
    path("<int:pk>/comprobante/", views.reserva_comprobante, name="reserva_comprobante"),
    path("<int:pk>/anular/", views.reserva_anular, name="reserva_anular"),
    path("<int:pk>/finalizar/", views.reserva_finalizar, name="reserva_finalizar"),
]
