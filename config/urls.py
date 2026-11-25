"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, path

from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('inicio/', views.inicio, name='inicio'),
    path('mi-actividad/', views.mi_actividad_mensual, name='mi_actividad_mensual'),
    path('privacidad/', views.privacidad, name='privacidad'),
    path('terminos/', views.terminos, name='terminos'),
    path('', include('usuarios.urls_autenticacion')),
    path('sedes/', include('instalaciones.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('reservas/', include('reservas.urls')),
    path('agenda/', include('agenda.urls')),
    path('clases/', include('clases.urls')),
    path('caja/', include('caja.urls')),
    path('reportes/', include('reportes.urls')),
    path('auditoria/', include('auditoria.urls')),
    path('comunicaciones/', include('comunicaciones.urls')),
    path('', include(([
        path('contrataciones/', include('membresias.urls_contrataciones')),
        path('catalogo/', include('membresias.urls_catalogo')),
        path('membresias/', include('membresias.urls')),
    ], 'membresias'))),
    path('oferta/', include('config.urls_oferta')),
]
