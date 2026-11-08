from django.urls import path

from . import views, vistas_devoluciones

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
    path("<int:pk>/", views.sesion_detalle, name="sesion_detalle"),
    path("<int:pk>/cerrar/", views.caja_cerrar, name="caja_cerrar"),
    path("<int:pk>/devoluciones/nueva/", vistas_devoluciones.devolucion_crear, name="devolucion_crear"),
]
