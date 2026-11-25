from django.urls import path

from . import vistas_continuidad, vistas_propias

urlpatterns = [
    path("mis-contrataciones/", vistas_propias.mis_contrataciones, name="mis_contrataciones"),
    path("mis-contrataciones/planes/<int:pk>/", vistas_propias.contratacion_propia_detalle, name="mi_plan_contratado"),
    path("mis-contrataciones/planes/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, name="mi_plan_comprobante"),
    path("mis-contrataciones/membresias/<int:pk>/uso/", vistas_propias.uso_membresia_propia, name="mi_membresia_uso"),
    path("mis-contrataciones/membresias/<int:pk>/", vistas_propias.contratacion_propia_detalle, {"tipo": "membresia"}, name="mi_membresia_contratado"),
    path("mis-contrataciones/membresias/<int:pk>/comprobante/", vistas_propias.contratacion_propia_comprobante, {"tipo": "membresia"}, name="mi_membresia_comprobante"),
    path("mis-contrataciones/planes/<int:pk>/continuidad/", vistas_continuidad.responder, name="mi_plan_continuidad"),
    path("mis-contrataciones/membresias/<int:pk>/continuidad/", vistas_continuidad.responder, {"tipo": "membresia"}, name="mi_membresia_continuidad"),
]
