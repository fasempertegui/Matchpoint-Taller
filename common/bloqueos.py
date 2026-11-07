from usuarios.models import Rol, Usuario


def bloquear_usuarios(usuarios_ids):
    list(
        Usuario.objects.select_for_update(of=("self",))
        .filter(pk__in=usuarios_ids, is_active=True, roles__rol__codigo=Rol.ADMINISTRADOR)
        .order_by("pk")
    )
    return {
        usuario.pk: usuario
        for usuario in Usuario.objects.select_for_update().filter(pk__in=usuarios_ids)
        .order_by("pk").prefetch_related("roles__rol")
    }
