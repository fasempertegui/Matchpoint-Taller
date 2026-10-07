from django.urls import reverse

from .models import Rol


def breadcrumbs_usuario(actor, usuario=None):
    breadcrumbs = [("Inicio", reverse("inicio"))]
    puede_consultar_usuarios = actor.has_perm("usuarios.view_usuario")
    if usuario is not None and actor.pk == usuario.pk:
        puede_consultar_perfil = puede_consultar_usuarios or actor.tiene_rol(Rol.PUBLICO)
        breadcrumbs.append((
            "Mi perfil",
            reverse("usuarios:usuario_detalle", args=[usuario.pk]) if puede_consultar_perfil else None,
        ))
    else:
        breadcrumbs.append((
            "Usuarios", reverse("usuarios:usuario_lista") if puede_consultar_usuarios else None,
        ))
        if usuario is not None:
            breadcrumbs.append((
                str(usuario),
                reverse("usuarios:usuario_detalle", args=[usuario.pk]) if puede_consultar_usuarios else None,
            ))
    return breadcrumbs
