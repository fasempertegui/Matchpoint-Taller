from django.urls import path

from . import vistas_ajustes, views, vistas_contrataciones, vistas_propias, vistas_continuidad

app_name = "membresias"

urlpatterns = [
    path("mis-contrataciones/", vistas_propias.mis_contrataciones, name="mis_contrataciones"),
    path("mis-contrataciones/planes/<int:pk>/", vistas_propias.contratacion_propia_detalle, name="mi_plan_contratado"),
    path("mis-contrataciones/planes/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, name="mi_plan_comprobante"),
    path("mis-contrataciones/membresias/<int:pk>/uso/", vistas_propias.uso_membresia_propia, name="mi_membresia_uso"),
    path("mis-contrataciones/membresias/<int:pk>/", vistas_propias.contratacion_propia_detalle, {"tipo": "membresia"}, name="mi_membresia_contratado"),
    path("mis-contrataciones/membresias/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, {"tipo": "membresia"}, name="mi_membresia_comprobante"),
    path("mis-contrataciones/planes/<int:pk>/continuidad/", vistas_continuidad.responder, name="mi_plan_continuidad"),
    path("mis-contrataciones/membresias/<int:pk>/continuidad/", vistas_continuidad.responder, {"tipo": "membresia"}, name="mi_membresia_continuidad"),
    path("continuidad/", vistas_continuidad.lista, name="continuidad_lista"),
    path("", views.catalogos, name="catalogos"),
    path("contrataciones/usuario/<int:usuario_id>/", vistas_contrataciones.contratacion_lista, name="contrataciones_usuario"),
    path("contrataciones/planes/", vistas_contrataciones.contratacion_lista, name="contratacion_plan_lista"),
    path("contrataciones/planes/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, name="contratacion_plan_buscar_usuarios"),
    path("contrataciones/planes/nueva/", vistas_contrataciones.contratacion_crear, name="contratacion_plan_crear"),
    path("contrataciones/planes/<int:pk>/", vistas_contrataciones.contratacion_detalle, name="contratacion_plan_detalle"),
    path("contrataciones/planes/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, name="contratacion_plan_anular"),
    path("contrataciones/planes/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, name="contratacion_plan_comprobante"),
    path("planes/", views.plan_lista, name="plan_lista"),
    path("planes/nuevo/", views.plan_formulario, name="plan_crear"),
    path("planes/<int:pk>/", views.plan_detalle, name="plan_detalle"),
    path("planes/<int:pk>/editar/", views.plan_formulario, name="plan_editar"),
    path("planes/<int:pk>/cambiar-estado/", views.plan_cambiar_estado, name="plan_cambiar_estado"),
    path("socios/", views.membresia_lista, name="membresia_lista"),
    path("socios/nueva/", views.membresia_formulario, name="membresia_crear"),
    path("socios/<int:pk>/", views.membresia_detalle, name="membresia_detalle"),
    path("socios/<int:pk>/editar/", views.membresia_formulario, name="membresia_editar"),
    path("socios/<int:pk>/cambiar-estado/", views.membresia_cambiar_estado, name="membresia_cambiar_estado"),
    path("contrataciones/membresias/", vistas_contrataciones.contratacion_lista, {"tipo": "membresia"}, name="contratacion_membresia_lista"),
    path("contrataciones/membresias/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, {"tipo": "membresia"}, name="contratacion_membresia_buscar_usuarios"),
    path("contrataciones/membresias/nueva/", vistas_contrataciones.contratacion_crear, {"tipo": "membresia"}, name="contratacion_membresia_crear"),
    path("contrataciones/membresias/<int:pk>/", vistas_contrataciones.contratacion_detalle, {"tipo": "membresia"}, name="contratacion_membresia_detalle"),
    path("contrataciones/membresias/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, {"tipo": "membresia"}, name="contratacion_membresia_comprobante"),
    path("contrataciones/membresias/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, {"tipo": "membresia"}, name="contratacion_membresia_anular"),
    path("contrataciones/membresias/<int:pk>/ajustar-horas/", vistas_ajustes.ajustar_horas, name="ajustar_horas"),
]
