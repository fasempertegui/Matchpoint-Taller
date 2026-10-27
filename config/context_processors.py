from django.urls import reverse

from usuarios.models import Rol


def navegacion(request):
    usuario = request.user
    if not usuario.is_authenticated or not usuario.is_active or usuario.debe_cambiar_contrasena:
        return {"navegacion_app": {}}
    roles = set(usuario.roles.values_list("rol__codigo", flat=True))
    administrador = Rol.ADMINISTRADOR in roles
    ruta = request.resolver_match
    namespace = ruta.namespace if ruta else ""
    nombre_vista = ruta.view_name if ruta else ""
    feriados_activo = namespace == "clases" and ruta.url_name.startswith("feriado_")
    clases_activo = namespace == "clases" and not feriados_activo
    perfil_activo = namespace == "usuarios" and ruta.kwargs.get("pk") == usuario.pk

    def enlace(nombre, destino, activo, descripcion, kwargs=None):
        url = reverse(destino, kwargs=kwargs)
        return {
            "nombre": nombre, "url": url, "activo": activo,
            "actual": request.path == url, "descripcion": descripcion,
        }

    agenda = enlace(
        "Agenda", "agenda:agenda", namespace in ("agenda", "reservas"),
        "Consultá tus clases y los horarios de las sedes." if not administrador
        else "Consulta de clases, reservas, bloqueos y disponibilidad de las canchas.",
    )
    clases = []
    if administrador:
        clases.append(enlace("Planilla semanal", "clases:planilla", clases_activo, "Programación habitual de clases."))
    elif roles.intersection((Rol.PROFESOR, Rol.ALUMNO)):
        clases.append(enlace(
            "Mi actividad", "clases:actividad_clases", clases_activo,
            "Consulta de tus clases y su historial.", {"usuario_id": usuario.pk},
        ))
    administracion = []
    if usuario.has_perm("usuarios.view_usuario"):
        administracion.append(enlace(
            "Usuarios", "usuarios:usuario_lista", namespace == "usuarios" and not perfil_activo,
            "Alta, consulta y gestión de usuarios, roles y acceso al sistema.",
        ))
    if usuario.has_perm("instalaciones.view_sede"):
        administracion.append(enlace(
            "Sedes y canchas", "instalaciones:sede_lista", namespace == "instalaciones",
            "Consulta y gestión de sedes, canchas, horarios y precios.",
        ))
    if administrador:
        administracion.append(enlace(
            "Feriados", "clases:feriado_lista", feriados_activo,
            "Consulta y gestión de feriados.",
        ))
    auditoria = enlace(
        "Auditoría", "auditoria:auditoria_lista", namespace == "auditoria",
        "Historial de operaciones y consulta de sus valores anteriores y actuales.",
    ) if administrador else None
    modulos_inicio = [{"nombre": "Agenda", "descripcion": agenda["descripcion"], "destino": agenda}]
    modulos_inicio.extend(
        {"nombre": item["nombre"], "descripcion": item["descripcion"], "destino": item}
        for item in administracion if item["nombre"] != "Feriados"
    )
    if clases:
        modulos_inicio.append({
            "nombre": "Clases",
            "descripcion": "Programación de clases, asignación de profesores y alumnos, y registro de asistencia.",
            "destino": clases[0], "boton": "Ver planilla semanal" if administrador else "Mi actividad",
        })
    if auditoria:
        modulos_inicio.append({"nombre": "Auditoría", "descripcion": auditoria["descripcion"], "destino": auditoria})
        administracion.append(auditoria)
    return {"navegacion_app": {
        "inicio_activo": nombre_vista == "inicio", "agenda": agenda,
        "clases": clases, "clases_activo": clases_activo,
        "administracion": administracion,
        "administracion_activo": any(item["activo"] for item in administracion),
        "perfil_activo": perfil_activo,
        "modulos_inicio": modulos_inicio, "mostrar_preparacion": administrador,
    }}
