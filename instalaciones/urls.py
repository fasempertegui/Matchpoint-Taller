from django.urls import path

from . import views, vistas_horarios_especiales

app_name = "instalaciones"

urlpatterns = [
    path("", views.sede_lista, name="sede_lista"),
    path("nueva/", views.sede_crear, name="sede_crear"),
    path(
        "nueva/buscar-direccion/",
        views.sede_buscar_direccion_crear,
        name="sede_buscar_direccion_crear",
    ),
    path("horarios-especiales/", vistas_horarios_especiales.horarios_especiales_lista, name="horarios_especiales"),
    path(
        "horarios-especiales/nuevo/",
        vistas_horarios_especiales.horario_especial_crear,
        name="horario_especial_crear",
    ),
    path(
        "horarios-especiales/<int:pk>/editar/",
        vistas_horarios_especiales.horario_especial_editar,
        name="horario_especial_editar",
    ),
    path(
        "horarios-especiales/<int:pk>/quitar/",
        vistas_horarios_especiales.horario_especial_quitar,
        name="horario_especial_quitar",
    ),
    path(
        "horarios-especiales/feriados/nuevo/",
        vistas_horarios_especiales.feriado_crear,
        name="feriado_crear",
    ),
    path(
        "horarios-especiales/feriados/<int:pk>/quitar/",
        vistas_horarios_especiales.feriado_quitar,
        name="feriado_quitar",
    ),
    path("<int:pk>/", views.sede_detalle, name="sede_detalle"),
    path("<int:pk>/editar/", views.sede_editar, name="sede_editar"),
    path(
        "<int:pk>/editar/buscar-direccion/",
        views.sede_buscar_direccion_editar,
        name="sede_buscar_direccion_editar",
    ),
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
