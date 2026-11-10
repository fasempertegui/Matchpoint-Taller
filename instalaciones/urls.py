from django.urls import path

from . import views, vistas_publicas

app_name = "instalaciones"

urlpatterns = [
    path("oferta/", vistas_publicas.sedes_publicas, name="publico_sedes"),
    path("oferta/sedes/<int:pk>/", vistas_publicas.sede_publica, name="publico_sede"),
    path("oferta/canchas/<int:pk>/", vistas_publicas.cancha_publica, name="publico_cancha"),
    path("", views.sede_lista, name="sede_lista"),
    path("nueva/", views.sede_crear, name="sede_crear"),
    path("<int:pk>/", views.sede_detalle, name="sede_detalle"),
    path("<int:pk>/editar/", views.sede_editar, name="sede_editar"),
    path("<int:pk>/precio/", views.sede_precio_configurar, name="sede_precio_configurar"),
    path("<int:pk>/horarios/", views.sede_horario_configurar, name="sede_horarios_configurar"),
    path(
        "<int:pk>/horarios/<int:dia>/",
        views.sede_horario_configurar,
        name="sede_horario_configurar",
    ),
    path("<int:pk>/cambiar-estado/", views.sede_cambiar_estado, name="sede_cambiar_estado"),
    path("<int:sede_pk>/canchas/nueva/", views.cancha_crear, name="cancha_crear"),
    path("<int:sede_pk>/canchas/<int:pk>/editar/", views.cancha_editar, name="cancha_editar"),
    path(
        "<int:sede_pk>/canchas/<int:pk>/cambiar-estado/",
        views.cancha_cambiar_estado,
        name="cancha_cambiar_estado",
    ),
]
