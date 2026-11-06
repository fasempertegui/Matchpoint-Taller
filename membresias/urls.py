from django.urls import path

from . import views, vistas_contrataciones, vistas_oferta, vistas_propias

app_name = "membresias"

urlpatterns = [
    path("mis-contrataciones/", vistas_propias.mis_contrataciones, name="mis_contrataciones"),
    path("mis-contrataciones/planes/<int:pk>/", vistas_propias.contratacion_propia_detalle, name="mi_plan_contratado"),
    path("mis-contrataciones/pases/<int:pk>/", vistas_propias.contratacion_propia_detalle, {"tipo": "pase"}, name="mi_pase_contratado"),
    path("mis-contrataciones/planes/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, name="mi_plan_comprobante"),
    path("mis-contrataciones/pases/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, {"tipo": "pase"}, name="mi_pase_comprobante"),
    path("oferta/", vistas_oferta.oferta, name="oferta"),
    path("oferta/planes/", vistas_oferta.oferta_planes, name="oferta_planes"),
    path("oferta/pases/", vistas_oferta.oferta_pases, name="oferta_pases"),
    path("oferta/tarifas/", vistas_oferta.oferta_tarifas, name="oferta_tarifas"),
    path("", views.catalogos, name="catalogos"),
    path("contrataciones/planes/", vistas_contrataciones.contratacion_lista, name="contratacion_plan_lista"),
    path("contrataciones/planes/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, name="contratacion_plan_buscar_usuarios"),
    path("contrataciones/pases/buscar-usuarios/", vistas_contrataciones.buscar_usuarios_contratacion, {"tipo": "pase"}, name="contratacion_pase_buscar_usuarios"),
    path("contrataciones/planes/nueva/", vistas_contrataciones.contratacion_crear, name="contratacion_plan_crear"),
    path("contrataciones/planes/<int:pk>/", vistas_contrataciones.contratacion_detalle, name="contratacion_plan_detalle"),
    path("contrataciones/planes/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, name="contratacion_plan_anular"),
    path("contrataciones/pases/", vistas_contrataciones.contratacion_lista, {"tipo": "pase"}, name="contratacion_pase_lista"),
    path("contrataciones/pases/nueva/", vistas_contrataciones.contratacion_crear, {"tipo": "pase"}, name="contratacion_pase_crear"),
    path("contrataciones/pases/<int:pk>/", vistas_contrataciones.contratacion_detalle, {"tipo": "pase"}, name="contratacion_pase_detalle"),
    path("contrataciones/pases/<int:pk>/anular/", vistas_contrataciones.contratacion_anular, {"tipo": "pase"}, name="contratacion_pase_anular"),
    path("contrataciones/planes/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, name="contratacion_plan_comprobante"),
    path("contrataciones/pases/<int:pk>/comprobante/", vistas_contrataciones.contratacion_comprobante, {"tipo": "pase"}, name="contratacion_pase_comprobante"),
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
