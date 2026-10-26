from django.urls import path

from . import views

app_name = "clases"

urlpatterns = [
    path("<int:pk>/", views.clase_detalle, name="clase_detalle"),
]
