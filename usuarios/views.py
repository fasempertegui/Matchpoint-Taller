from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import (
    UsuarioBusquedaForm,
    UsuarioCrearForm,
    UsuarioEditarForm,
    generar_contrasena,
    generar_contrasena_valida,
    sugerir_nombre_usuario,
)
from .models import Rol, Usuario, UsuarioRol

ROLES_GESTIONABLES = {Rol.RESERVAS, Rol.PROFESOR, Rol.ALUMNO}


@login_required
@permission_required("usuarios.view_usuario", raise_exception=True)
def usuario_lista(request):
    formulario_busqueda = UsuarioBusquedaForm(request.GET or None)
    usuarios = Usuario.objects.annotate(
        es_administrador_listado=Exists(
            UsuarioRol.objects.filter(
                usuario_id=OuterRef("pk"),
                rol__codigo=Rol.ADMINISTRADOR,
            )
        )
    ).order_by("first_name", "last_name")

    if formulario_busqueda.is_valid():
        q = formulario_busqueda.cleaned_data.get("q")
        rol = formulario_busqueda.cleaned_data.get("rol")
        estado = formulario_busqueda.cleaned_data.get("estado")
        if q:
            usuarios = usuarios.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(username__icontains=q)
            )
        if rol:
            usuarios = usuarios.filter(roles__rol=rol)
        if estado:
            usuarios = usuarios.filter(is_active=estado == "activo")

    return render(
        request,
        "usuarios/usuario_lista.html",
        {"usuarios": usuarios, "formulario_busqueda": formulario_busqueda},
    )


@login_required
def usuario_detalle(request, pk):
    if not request.user.has_perm("usuarios.view_usuario") and (
        request.user.pk != pk or not request.user.tiene_rol(Rol.PUBLICO)
    ):
        raise PermissionDenied
    usuario = get_object_or_404(
        Usuario.objects.prefetch_related("roles__rol"), pk=pk
    )
    roles_asignados = [asignacion.rol for asignacion in usuario.roles.all()]
    roles_actuales = {rol.codigo for rol in roles_asignados}
    return render(
        request,
        "usuarios/usuario_detalle.html",
        {
            "usuario_obj": usuario,
            "roles_actuales": roles_actuales,
            "roles_asignados": roles_asignados,
            "usuario_es_administrador": Rol.ADMINISTRADOR in roles_actuales,
            "rol_reservas": Rol.RESERVAS,
            "rol_profesor": Rol.PROFESOR,
            "rol_alumno": Rol.ALUMNO,
        },
    )


@login_required
@permission_required("usuarios.add_usuario", raise_exception=True)
@require_http_methods(["GET", "POST"])
def usuario_crear(request):
    if request.method == "POST":
        formulario = UsuarioCrearForm(request.POST)
        if formulario.is_valid():
            usuario = formulario.guardar()
            return render(
                request,
                "usuarios/usuario_creado.html",
                {
                    "usuario_obj": usuario,
                    "contrasena": formulario.cleaned_data["contrasena"],
                },
            )
        return render(request, "usuarios/usuario_formulario.html", {"formulario": formulario})

    formulario = UsuarioCrearForm()
    return render(request, "usuarios/usuario_formulario.html", {"formulario": formulario})


@login_required
@permission_required("usuarios.add_usuario", raise_exception=True)
@require_GET
def usuario_sugerir_nombre(request):
    nombre = request.GET.get("nombre", "").strip()
    apellido = request.GET.get("apellido", "").strip()
    if not nombre or not apellido:
        return JsonResponse(
            {"error": "Ingresá el nombre y el apellido antes de generar el usuario."},
            status=400,
        )

    try:
        nombre_usuario = sugerir_nombre_usuario(nombre, apellido)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)
    return JsonResponse({"nombre_usuario": nombre_usuario})


@login_required
@permission_required("usuarios.add_usuario", raise_exception=True)
@require_GET
def usuario_sugerir_contrasena(request):
    return JsonResponse({"contrasena": generar_contrasena()})


@login_required
@permission_required("usuarios.change_usuario", raise_exception=True)
@require_http_methods(["GET", "POST"])
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    formulario = UsuarioEditarForm(request.POST or None, instance=usuario)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, f'El correo de "{usuario}" fue actualizado.')
        return redirect("usuarios:usuario_detalle", pk=usuario.pk)

    return render(
        request,
        "usuarios/usuario_editar.html",
        {"formulario": formulario, "usuario_obj": usuario},
    )


@login_required
@permission_required("usuarios.change_usuario", raise_exception=True)
@require_http_methods(["GET", "POST"])
def usuario_restablecer_contrasena(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(
            request,
            "No podés restablecer tu propia contraseña. Usá la opción para cambiarla.",
        )
        return redirect("usuarios:usuario_detalle", pk=usuario.pk)

    if request.method == "POST":
        with transaction.atomic():
            usuario = get_object_or_404(
                Usuario.objects.select_for_update(), pk=pk
            )
            contrasena = generar_contrasena_valida(usuario)
            usuario.set_password(contrasena)
            usuario.debe_cambiar_contrasena = True
            usuario.save(
                update_fields=["password", "debe_cambiar_contrasena", "actualizado_en"]
            )

        return render(
            request,
            "usuarios/usuario_contrasena_restablecida.html",
            {"usuario_obj": usuario, "contrasena": contrasena},
        )

    return render(
        request,
        "usuarios/usuario_restablecer_contrasena.html",
        {"usuario_obj": usuario},
    )


@login_required
@permission_required("usuarios.change_usuario", raise_exception=True)
@require_http_methods(["GET", "POST"])
def usuario_cambiar_estado(request, pk):
    if request.method == "POST":
        # Todas las solicitudes toman primero los mismos bloqueos y en el mismo
        # orden para que dos cambios concurrentes no dejen cero administradores.
        with transaction.atomic():
            administradores_activos = list(
                Usuario.objects.select_for_update(of=("self",))
                .filter(
                    is_active=True,
                    roles__rol__codigo=Rol.ADMINISTRADOR,
                )
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            usuario = get_object_or_404(
                Usuario.objects.select_for_update(), pk=pk
            )
            activar = not usuario.is_active

            if not activar and usuario.pk == request.user.pk:
                messages.error(request, "No podés desactivar tu propia cuenta.")
                return redirect("usuarios:usuario_detalle", pk=usuario.pk)

            if (
                not activar
                and usuario.tiene_rol(Rol.ADMINISTRADOR)
                and len(administradores_activos) <= 1
            ):
                messages.error(
                    request,
                    "No se puede desactivar al último administrador activo.",
                )
                return redirect("usuarios:usuario_detalle", pk=usuario.pk)

            usuario.is_active = activar
            usuario.fecha_baja = None if activar else timezone.now()
            usuario.save(update_fields=["is_active", "fecha_baja", "actualizado_en"])

        messages.success(
            request,
            f'El usuario "{usuario}" quedó {"activo" if activar else "inactivo"}.',
        )
        return redirect("usuarios:usuario_detalle", pk=usuario.pk)

    usuario = get_object_or_404(Usuario, pk=pk)
    activar = not usuario.is_active
    return render(
        request,
        "usuarios/usuario_confirmar_cambio_estado.html",
        {"usuario_obj": usuario, "activar": activar},
    )


@login_required
@permission_required("usuarios.change_usuario", raise_exception=True)
@require_http_methods(["POST"])
def usuario_rol_toggle(request, pk, rol):
    if rol not in ROLES_GESTIONABLES:
        usuario = get_object_or_404(Usuario, pk=pk)
        messages.error(request, "Ese rol no se gestiona desde acá.")
        return redirect("usuarios:usuario_detalle", pk=usuario.pk)

    rol_obj = get_object_or_404(Rol, codigo=rol)
    with transaction.atomic():
        usuario = get_object_or_404(
            Usuario.objects.select_for_update(), pk=pk
        )
        asignacion = (
            UsuarioRol.objects.select_for_update()
            .filter(usuario=usuario, rol=rol_obj)
            .first()
        )

        if asignacion:
            asignacion.delete()
            messages.success(request, f"Se quitó el rol {rol_obj.nombre}.")
        else:
            UsuarioRol.objects.create(
                usuario=usuario, rol=rol_obj, asignado_por=request.user
            )
            messages.success(request, f"Se asignó el rol {rol_obj.nombre}.")

    return redirect(reverse("usuarios:usuario_detalle", args=[usuario.pk]) + "#roles")
