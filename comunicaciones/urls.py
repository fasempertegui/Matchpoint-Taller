from django.urls import path

from .views import envios_lista

app_name = "comunicaciones"
urlpatterns = [path("", envios_lista, name="envios_lista")]
