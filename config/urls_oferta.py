from django.urls import path

from instalaciones.vistas_publicas import sedes_publicas
from membresias.vistas_oferta import oferta, oferta_membresias, oferta_planes

app_name = "oferta"

urlpatterns = [
    path("", oferta, name="inicio"),
    path("sedes/", sedes_publicas, name="sedes"),
    path("planes/", oferta_planes, name="planes"),
    path("membresias/", oferta_membresias, name="membresias"),
]
