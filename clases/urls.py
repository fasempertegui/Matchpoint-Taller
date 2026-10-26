from django.urls import path

from . import views

app_name = "clases"

urlpatterns = [
    path("actividad/<int:usuario_id>/", views.actividad_clases, name="actividad_clases"),
    path("<int:pk>/asistencia/", views.clase_asistencia, name="clase_asistencia"),
    path("<int:pk>/asistencia/personas/", views.buscar_personas_asistencia, name="buscar_personas_asistencia"),
    path("<int:pk>/finalizar/", views.clase_finalizar, name="clase_finalizar"),
    path("<int:pk>/anular/", views.clase_anular, name="clase_anular"),
    path("<int:pk>/anular-bloquear/", views.clase_anular, {"bloquear": True}, name="clase_anular_bloquear"),
    path("crear/", views.clase_crear, name="clase_crear"),
    path("personas/", views.buscar_personas, name="buscar_personas"),
    path("<int:pk>/", views.clase_detalle, name="clase_detalle"),
    path("<int:pk>/editar/", views.clase_editar, name="clase_editar"),
    path("<int:pk>/cambiar-cancha/", views.clase_cambiar_cancha, name="clase_cambiar_cancha"),
]
