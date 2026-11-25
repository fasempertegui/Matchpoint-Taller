from django.urls import path

from . import views

urlpatterns = [
    path("planes/", views.plan_lista, name="plan_lista"),
    path("planes/nuevo/", views.plan_formulario, name="plan_crear"),
    path("planes/<int:pk>/", views.plan_detalle, name="plan_detalle"),
    path("planes/<int:pk>/editar/", views.plan_formulario, name="plan_editar"),
    path("planes/<int:pk>/cambiar-estado/", views.plan_cambiar_estado, name="plan_cambiar_estado"),
    path("membresias/", views.membresia_lista, name="membresia_lista"),
    path("membresias/nueva/", views.membresia_formulario, name="membresia_crear"),
    path("membresias/<int:pk>/", views.membresia_detalle, name="membresia_detalle"),
    path("membresias/<int:pk>/editar/", views.membresia_formulario, name="membresia_editar"),
    path("membresias/<int:pk>/cambiar-estado/", views.membresia_cambiar_estado, name="membresia_cambiar_estado"),
]
