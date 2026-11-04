import logging

from django.db import DatabaseError, transaction
from django.utils import timezone

from usuarios.models import Rol

from .models import IntentoAuditoria


logger = logging.getLogger(__name__)


def registrar_intento(request, tipo, motivo, *, identificador_ingresado=""):
    if getattr(request, "_intento_auditoria", None) is not None:
        return
    ruta = request.resolver_match
    if ruta is None:
        return
    parametros = {
        nombre: valor for nombre, valor in ruta.kwargs.items()
        if nombre in ("pk", "sede_pk", "usuario_id", "dia") and type(valor) is int
    }
    if ruta.kwargs.get("rol") in (Rol.ADMINISTRADOR, Rol.PROFESOR, Rol.ALUMNO, Rol.RESERVAS, Rol.PUBLICO):
        parametros["rol"] = ruta.kwargs["rol"]
    usuario_id = request.user.pk if request.user.is_authenticated else None
    if tipo == IntentoAuditoria.Tipo.INICIO_SESION_FALLIDO:
        usuario_id = None
    # Se persiste al salir de la transacción de negocio, incluso si ésta se revierte.
    request._intento_auditoria = {
        "solicitud_id": request.solicitud_auditoria_id,
        "realizado_en": timezone.now(), "usuario_id": usuario_id, "tipo": tipo, "motivo": motivo,
        "vista": ruta.view_name, "metodo": request.method, "parametros_destino": parametros,
        "identificador_ingresado": identificador_ingresado[:150] if tipo == IntentoAuditoria.Tipo.INICIO_SESION_FALLIDO else "",
    }


def guardar_intento(request):
    intento = getattr(request, "_intento_auditoria", None)
    if intento is None:
        return
    try:
        with transaction.atomic():
            IntentoAuditoria.objects.create(**intento)
    except DatabaseError:
        logger.error("No se pudo persistir el intento de la solicitud %s.", intento["solicitud_id"])
