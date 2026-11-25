from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("eventos/", views.eventos_lista, name="eventos_lista"),
    path("eventos/clases/", views.eventos_lista, {"tipo": "clase"}, name="eventos_clases"),
    path("eventos/reservas/", views.eventos_lista, {"tipo": "reserva"}, name="eventos_reservas"),
    path("eventos/bloqueos/", views.eventos_lista, {"tipo": "bloqueo"}, name="eventos_bloqueos"),
    path("acciones/", views.agenda_acciones, name="acciones"),
    path("bloqueos/crear/", views.bloqueo_crear, name="bloqueo_crear"),
    path("bloqueos/<int:pk>/", views.bloqueo_detalle, name="bloqueo_detalle"),
    path("bloqueos/<int:pk>/anular/", views.bloqueo_anular, name="bloqueo_anular"),
    path("organizadores/", views.buscar_organizadores, name="buscar_organizadores"),
]
