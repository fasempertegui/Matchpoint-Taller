from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve


class CambioContrasenaObligatorioMiddleware:
    urls_permitidas = {
        "login",
        "logout",
        "password_change",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        if (
            usuario.is_authenticated
            and usuario.debe_cambiar_contrasena
            and not self._ruta_permitida(request.path_info)
        ):
            return redirect("password_change")
        return self.get_response(request)

    def _ruta_permitida(self, ruta):
        if settings.STATIC_URL and ruta.startswith(settings.STATIC_URL):
            return True
        try:
            coincidencia = resolve(ruta)
        except Resolver404:
            return False
        return coincidencia.url_name in self.urls_permitidas
