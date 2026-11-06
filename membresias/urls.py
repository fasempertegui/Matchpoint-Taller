from django.urls import path

from . import views, vistas_contrataciones, vistas_oferta, vistas_propias

app_name = "membresias"

urlpatterns = [
    path("mis-contrataciones/", vistas_propias.mis_contrataciones, name="mis_contrataciones"),
    path("mis-contrataciones/planes/<int:pk>/", vistas_propias.contratacion_propia_detalle, name="mi_plan_contratado"),
    path("mis-contrataciones/planes/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, name="mi_plan_comprobante"),
    path("oferta/", vistas_oferta.oferta, name="oferta"),
    path("oferta/planes/", vistas_oferta.oferta_planes, name="oferta_planes"),
    path("oferta/tarifas/", vistas_oferta.oferta_tarifas, name="oferta_tarifas"),
    path("", views.catalogos, name="catalogos"),
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
]
