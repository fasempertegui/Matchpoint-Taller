from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("bloqueos/<int:pk>/", views.bloqueo_detalle, name="bloqueo_detalle"),
    path("organizadores/", views.buscar_organizadores, name="buscar_organizadores"),
]
