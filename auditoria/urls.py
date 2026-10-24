from django.urls import path

from . import views


app_name = "auditoria"
urlpatterns = [path("", views.auditoria_lista, name="auditoria_lista")]
