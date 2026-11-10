from django.core.exceptions import PermissionDenied

from usuarios.models import Rol, Usuario
from usuarios.acceso import exigir_acceso_operativo

from .models import ClaseProfesor


def exigir_acceso_clases(usuario):
    return exigir_acceso_operativo(usuario)

def exigir_administracion_clases(usuario):
    usuario = exigir_acceso_clases(usuario)
    if not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    return usuario


def puede_dictar_clase(usuario, clase):
    if usuario is None or not usuario.is_authenticated:
        return False
    return ClaseProfesor.objects.filter(
        clase=clase,
        profesor_id=usuario.pk,
        profesor__is_active=True,
        profesor__correo_verificado_en__isnull=False,
        profesor__debe_cambiar_contrasena=False,
        profesor__roles__rol__codigo=Rol.PROFESOR,
    ).exists()
