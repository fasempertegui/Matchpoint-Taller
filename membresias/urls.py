from django.urls import path

from . import views

app_name = "membresias"

urlpatterns = [
    path("", views.catalogos, name="catalogos"),
    path("pases/", views.pase_lista, name="pase_lista"),
    path("pases/nuevo/", views.pase_formulario, name="pase_crear"),
    path("pases/<int:pk>/", views.pase_detalle, name="pase_detalle"),
    path("pases/<int:pk>/editar/", views.pase_formulario, name="pase_editar"),
    path("pases/<int:pk>/cambiar-estado/", views.pase_cambiar_estado, name="pase_cambiar_estado"),
    path("planes/", views.plan_lista, name="plan_lista"),
    path("planes/nuevo/", views.plan_formulario, name="plan_crear"),
    path("planes/<int:pk>/", views.plan_detalle, name="plan_detalle"),
    path("planes/<int:pk>/editar/", views.plan_formulario, name="plan_editar"),
    path("planes/<int:pk>/cambiar-estado/", views.plan_cambiar_estado, name="plan_cambiar_estado"),
]
