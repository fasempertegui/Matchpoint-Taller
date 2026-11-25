from django.urls import path

from . import vistas_ajustes, vistas_continuidad, vistas_contrataciones

urlpatterns = [
    path("continuidad/", vistas_continuidad.lista, name="continuidad_lista"),
    path("usuario/<int:usuario_id>/", vistas_contrataciones.contratacion_lista, name="contrataciones_usuario"),
    path("por-cubrir/", vistas_contrataciones.contrataciones_por_cubrir, name="contrataciones_por_cubrir"),
    path("planes/", vistas_contrataciones.contratacion_lista, name="contratacion_plan_lista"),
    path("planes/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, name="contratacion_plan_buscar_usuarios"),
    path("planes/nueva/", vistas_contrataciones.contratacion_crear, name="contratacion_plan_crear"),
    path("planes/<int:pk>/", vistas_contrataciones.contratacion_detalle, name="contratacion_plan_detalle"),
    path("planes/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, name="contratacion_plan_anular"),
    path("planes/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, name="contratacion_plan_comprobante"),
    path("membresias/", vistas_contrataciones.contratacion_lista, {"tipo": "membresia"}, name="contratacion_membresia_lista"),
    path("membresias/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, {"tipo": "membresia"}, name="contratacion_membresia_buscar_usuarios"),
    path("membresias/nueva/", vistas_contrataciones.contratacion_crear, {"tipo": "membresia"}, name="contratacion_membresia_crear"),
    path("membresias/<int:pk>/", vistas_contrataciones.contratacion_detalle, {"tipo": "membresia"}, name="contratacion_membresia_detalle"),
    path("membresias/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, {"tipo": "membresia"}, name="contratacion_membresia_comprobante"),
    path("membresias/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, {"tipo": "membresia"}, name="contratacion_membresia_anular"),
    path("membresias/<int:pk>/ajustar-horas/", vistas_ajustes.ajustar_horas, name="ajustar_horas"),
]
