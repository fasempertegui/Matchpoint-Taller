import unicodedata
from functools import wraps

from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django_ratelimit.core import get_usage
from redis.exceptions import RedisError


def ip_y_usuario(_grupo, request):
    usuario = unicodedata.normalize("NFKC", request.POST.get("username", "").strip()).casefold()
    return f"{request.META['REMOTE_ADDR']}:{usuario}"


def limitar_solicitudes(grupo, *limites):
    def decorar(vista):
        @wraps(vista)
        @never_cache
        def vista_limitada(request, *args, **kwargs):
            for clave, frecuencia in limites:
                try:
                    uso = get_usage(
                        request,
                        group=grupo,
                        key=clave,
                        rate=frecuencia,
                        method="POST",
                        increment=True,
                    )
                except RedisError:
                    break
                if uso is None or not uso["should_limit"]:
                    continue
                if uso["time_left"] < 0:
                    break
                respuesta = render(request, "autenticacion/limite_solicitudes.html", status=429)
                respuesta["Retry-After"] = str(max(1, uso["time_left"]))
                return respuesta
            else:
                return vista(request, *args, **kwargs)

            return render(
                request, "autenticacion/limite_solicitudes.html", {"servicio_no_disponible": True}, status=503,
            )

        return vista_limitada

    return decorar
