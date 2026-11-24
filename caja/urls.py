from django.urls import path

from . import views, vistas_ajustes, vistas_devoluciones, vistas_excedentes

app_name = "caja"
urlpatterns = [
    path("", views.caja_actual, name="caja_actual"),
    path("historial/", views.historial_sesiones, name="historial_sesiones"),
    path("movimientos/", views.movimiento_lista, name="movimiento_lista"),
    path("movimientos/<int:pk>/anular/", views.movimiento_anular, name="movimiento_anular"),
    path("<int:pk>/movimientos/nuevo/", views.movimiento_crear, name="movimiento_crear"),
    path("abrir/", views.caja_abrir, name="caja_abrir"),
    path("movimientos/<int:pk>/", views.movimiento_detalle, name="movimiento_detalle"),
    path("<int:pk>/ingresos/nuevo/", views.ingreso_crear, name="ingreso_crear"),
    path("<int:pk>/ingresos/excedente/<str:tipo>/<int:origen_id>/", vistas_excedentes.ingreso_excedente, name="ingreso_excedente"),
    path("importes/<str:tipo>/<int:origen_id>/ajustar/", vistas_ajustes.ajustar_importe, name="ajustar_importe"),
    path("<int:pk>/", views.sesion_detalle, name="sesion_detalle"),
    path("<int:pk>/cerrar/", views.caja_cerrar, name="caja_cerrar"),
    path("<int:pk>/diferencias/<str:momento>/revisar/", views.revision_diferencia, name="revision_diferencia"),
    path("<int:pk>/devoluciones/nueva/", vistas_devoluciones.devolucion_crear, name="devolucion_crear"),
]
