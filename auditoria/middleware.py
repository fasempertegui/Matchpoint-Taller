from django.db import transaction

from .contexto import contexto_auditoria


class ContextoAuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user if request.user.is_authenticated else None
        with contexto_auditoria(usuario):
            respuesta = self.get_response(request)
            if respuesta.status_code >= 400:
                transaction.set_rollback(True)
            return respuesta
