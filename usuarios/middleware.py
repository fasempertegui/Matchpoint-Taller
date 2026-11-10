from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .models import Rol


class CambioContrasenaObligatorioMiddleware:
    urls_cuenta = {"login", "logout", "password_change", "password_change_done", "estado_verificacion", "confirmar_verificacion", "solicitar_verificacion", "corregir_correo", "password_reset", "password_reset_done", "password_reset_confirm", "password_reset_complete", "confirmar_cambio_correo"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        if usuario.is_authenticated:
            try:
                ruta = resolve(request.path_info)
            except Resolver404:
                return self.get_response(request)
            if ruta.url_name in self.urls_cuenta and not ruta.namespace:
                return self.get_response(request)
            if usuario.correo_verificado_en is None:
                if usuario.tiene_rol(Rol.ADMINISTRADOR):
                    return redirect("estado_verificacion")
                lectura = request.method == "GET" and (
                    ruta.view_name == "inicio"
                    or (ruta.view_name == "usuarios:usuario_detalle" and ruta.kwargs.get("pk") == usuario.pk)
                    or (ruta.namespace == "membresias" and ruta.url_name.startswith("oferta"))
                    or (ruta.namespace == "instalaciones" and ruta.url_name.startswith("publico_"))
                )
                if not lectura:
                    raise PermissionDenied
            if usuario.debe_cambiar_contrasena:
                return redirect("password_change")
        return self.get_response(request)
