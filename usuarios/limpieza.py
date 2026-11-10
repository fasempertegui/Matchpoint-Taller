from datetime import timedelta

from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from auditoria.models import IntentoAuditoria, LogAuditoria

from .models import LimpiezaCuenta, Rol, Usuario, UsuarioRol


@transaction.atomic
def limpiar_cuenta_inicial(usuario_id, *, ahora=None):
    ahora = ahora or timezone.now()
    usuario = Usuario.objects.select_for_update().filter(pk=usuario_id).first()
    if usuario is None or usuario.correo_verificado_en is not None or usuario.date_joined > ahora - timedelta(days=7):
        return False
    roles = set(usuario.roles.values_list("rol__codigo", flat=True))
    roles_iniciales = {Rol.ADMINISTRADOR} if usuario.is_superuser or Rol.ADMINISTRADOR in roles else {Rol.PUBLICO}
    incompatibilidad = roles != roles_iniciales
    if usuario.groups.exists() or usuario.user_permissions.exists():
        incompatibilidad = True
    for relacion in Usuario._meta.related_objects:
        if relacion.related_model in (IntentoAuditoria, LogAuditoria):
            continue
        if relacion.related_model == UsuarioRol and relacion.field.name == "usuario":
            continue
        if relacion.related_model.objects.filter(**{relacion.field.name: usuario.pk}).exists():
            incompatibilidad = True
            break
    if not incompatibilidad:
        try:
            with transaction.atomic(), contexto_auditoria(origen="tarea"):
                usuario.delete()
        except (ProtectedError, RestrictedError):
            incompatibilidad = True
    LimpiezaCuenta.objects.create(
        usuario_eliminado_id=usuario_id, procesado_en=ahora,
        resultado="inconsistente" if incompatibilidad else "eliminada",
        detalle="La cuenta tiene relaciones incompatibles con un alta inicial." if incompatibilidad else "",
    )
    return not incompatibilidad


def limpiar_cuentas_sin_verificar():
    ahora = timezone.now()
    ids = Usuario.objects.filter(correo_verificado_en__isnull=True, date_joined__lte=ahora - timedelta(days=7)).values_list("pk", flat=True)
    return sum(limpiar_cuenta_inicial(pk, ahora=ahora) for pk in list(ids))
