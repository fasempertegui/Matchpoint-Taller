from django.core.exceptions import PermissionDenied

from usuarios.models import Rol, Usuario

from .models import ClaseProfesor


def exigir_acceso_clases(usuario):
    if usuario is None or not usuario.is_authenticated:
        raise PermissionDenied
    try:
        return Usuario.objects.get(
            pk=usuario.pk,
            is_active=True,
            debe_cambiar_contrasena=False,
        )
    except Usuario.DoesNotExist:
        raise PermissionDenied from None


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
        estado=ClaseProfesor.Estado.ACTIVO,
        profesor_id=usuario.pk,
        profesor__is_active=True,
        profesor__debe_cambiar_contrasena=False,
        profesor__roles__rol__codigo=Rol.PROFESOR,
    ).exists()
