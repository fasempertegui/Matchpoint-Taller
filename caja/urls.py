from django.urls import path

from . import views

app_name = "caja"
urlpatterns = [
    path("", views.caja_actual, name="caja_actual"),
    path("abrir/", views.caja_abrir, name="caja_abrir"),
    path("<int:pk>/", views.sesion_detalle, name="sesion_detalle"),
    path("<int:pk>/cerrar/", views.caja_cerrar, name="caja_cerrar"),
]
