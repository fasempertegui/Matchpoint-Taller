from django.urls import path

from . import views

app_name = "clases"

urlpatterns = [
    path("crear/", views.clase_crear, name="clase_crear"),
    path("personas/", views.buscar_personas, name="buscar_personas"),
    path("<int:pk>/", views.clase_detalle, name="clase_detalle"),
    path("<int:pk>/editar/", views.clase_editar, name="clase_editar"),
]
