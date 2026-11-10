from django.core.exceptions import PermissionDenied

from .models import Usuario


def exigir_acceso_operativo(usuario, *, bloquear=False):
    if usuario is None or not usuario.is_authenticated:
        raise PermissionDenied
    consulta = Usuario.objects.habilitados().filter(debe_cambiar_contrasena=False)
    if bloquear:
        consulta = consulta.select_for_update()
    actual = consulta.filter(pk=usuario.pk).first()
    if actual is None:
        raise PermissionDenied
    return actual
