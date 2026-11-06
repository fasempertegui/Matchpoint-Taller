from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.models import Reserva

from .contexto import contexto_auditoria
from .intentos import guardar_intento, registrar_intento
from .models import IntentoAuditoria


class ContextoAuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user if request.user.is_authenticated else None
        try:
            with contexto_auditoria(usuario) as solicitud_id:
                request.solicitud_auditoria_id = solicitud_id
                respuesta = self.get_response(request)
                if respuesta.status_code >= 400:
                    transaction.set_rollback(True)
        finally:
            guardar_intento(request)
        return respuesta

    def process_exception(self, request, exception):
        ruta = request.resolver_match
        if ruta is None:
            return None
        if isinstance(exception, PermissionDenied) and ruta.namespace in (
            "usuarios", "instalaciones", "clases", "reservas", "agenda", "membresias", "auditoria",
        ):
            registrar_intento(
                request, IntentoAuditoria.Tipo.ACCESO_DENEGADO, IntentoAuditoria.Motivo.PERMISOS_INSUFICIENTES,
            )
        elif isinstance(exception, Http404) and request.user.is_authenticated:
            destinos_privados = {
                "reservas:reserva_detalle": (Reserva, "organizador_id"),
                "reservas:reserva_comprobante": (Reserva, "organizador_id"),
                "membresias:mi_plan_comprobante": (PlanUsuario, "usuario_id"),
                "membresias:mi_plan_contratado": (PlanUsuario, "usuario_id"),
                "membresias:mi_membresia_comprobante": (MembresiaUsuario, "usuario_id"),
                "membresias:mi_membresia_contratado": (MembresiaUsuario, "usuario_id"),
            }
            destino = destinos_privados.get(ruta.view_name)
            if destino:
                modelo, campo_titular = destino
                if modelo.objects.filter(pk=ruta.kwargs["pk"]).exclude(**{campo_titular: request.user.pk}).exists():
                    registrar_intento(
                        request, IntentoAuditoria.Tipo.ACCESO_DENEGADO, IntentoAuditoria.Motivo.REGISTRO_AJENO,
                    )
        return None
