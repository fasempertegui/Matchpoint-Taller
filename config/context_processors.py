from django.urls import reverse

from comunicaciones.models import Notificacion
from usuarios.models import Rol


DESTINOS_NAVEGACION = {
    "inicio": ("casa", "actividad"),
    "agenda:agenda": ("calendario", "actividad"),
    "clases:planilla": ("planilla", "actividad"),
    "clases:actividad_clases": ("pelota", "actividad"),
    "reservas:mis_reservas": ("calendario", "actividad"),
    "reservas:mis_invitaciones": ("correo", "actividad"),
    "membresias:mis_contrataciones": ("cartera", "actividad"),
    "usuarios:usuario_lista": ("usuarios", "gestion"),
    "membresias:contratacion_general_lista": ("cartera", "gestion"),
    "caja:caja_actual": ("dinero-cuadrado", "gestion"),
    "reportes:inicio": ("auditoria", "seguimiento"),
    "instalaciones:sede_lista": ("ciudad", "academia"),
    "instalaciones:horarios_especiales": ("reloj", "academia"),
    "membresias:plan_lista": ("libro", "academia"),
    "clases:feriado_lista": ("calendario", "academia"),
    "oferta:inicio": ("libro", "academia"),
    "comunicaciones:envios_lista": ("correo", "seguimiento"),
    "auditoria:auditoria_lista": ("auditoria", "seguimiento"),
}


def navegacion(request):
    usuario = request.user
    ruta = request.resolver_match
    solo_marca = ruta is not None and ruta.view_name == "confirmar_verificacion"
    if not usuario.is_authenticated or not usuario.is_active or usuario.debe_cambiar_contrasena:
        return {"navegacion_app": {"solo_marca": solo_marca}}
    roles = set(usuario.roles.values_list("rol__codigo", flat=True))
    administrador = Rol.ADMINISTRADOR in roles and usuario.esta_habilitado
    namespace = ruta.namespace if ruta else ""
    nombre_vista = ruta.view_name if ruta else ""
    feriados_activo = namespace == "clases" and ruta.url_name.startswith("feriado_")
    horarios_especiales_activo = feriados_activo or (
        namespace == "instalaciones"
        and ruta.url_name.startswith(("horarios_especiales", "horario_especial_", "feriado_"))
    )
    sedes_activo = namespace == "instalaciones" and not horarios_especiales_activo
    planilla_activa = namespace == "clases" and ruta.url_name.startswith(("planilla", "generacion_"))
    clases_concretas = namespace == "clases" and not feriados_activo and not planilla_activa
    clases_activo = planilla_activa if administrador else clases_concretas
    invitaciones_propias_activo = not administrador and namespace == "reservas" and (
        ruta.url_name in ("mis_invitaciones", "reserva_responder")
        or getattr(request, "detalle_invitacion", False)
    )
    reservas_propias_activo = not administrador and not invitaciones_propias_activo and namespace == "reservas" and ruta.url_name in (
        "mis_reservas", "reserva_detalle", "reserva_comprobante", "reserva_anular",
        "reserva_invitados", "reserva_socios", "reserva_resultado",
    )
    agenda_activa = (namespace in ("agenda", "reservas") and not (reservas_propias_activo or invitaciones_propias_activo)) or (administrador and clases_concretas)
    perfil_activo = namespace == "usuarios" and ruta.kwargs.get("pk") == usuario.pk
    contrataciones_propias_activo = namespace == "membresias" and ruta.url_name in (
        "mis_contrataciones", "mi_plan_contratado", "mi_membresia_contratado",
        "mi_plan_comprobante", "mi_membresia_comprobante", "mi_plan_continuidad", "mi_membresia_continuidad",
        "mi_membresia_uso",
    )
    catalogo_oferta_activo = namespace == "membresias" and ruta.url_name.startswith(("plan_", "membresia_"))
    contrataciones_admin_activo = (
        namespace == "membresias"
        and not contrataciones_propias_activo
        and not catalogo_oferta_activo
    )

    def enlace(nombre, destino, activo, descripcion, kwargs=None):
        url = reverse(destino, kwargs=kwargs)
        icono, grupo = DESTINOS_NAVEGACION[destino]
        return {
            "nombre": nombre, "url": url, "activo": activo,
            "actual": request.path == url, "descripcion": descripcion,
            "destino": destino, "icono": icono, "grupo": grupo,
        }

    agenda = enlace(
        "Agenda", "agenda:agenda", agenda_activa,
        "Consultá tus clases y los horarios de las sedes." if not administrador
        else "Consulta de clases, reservas, bloqueos y disponibilidad de las canchas.",
    )
    if not usuario.esta_habilitado:
        agenda = None
    oferta = enlace(
        "Oferta", "oferta:inicio", namespace == "oferta",
        "Sedes y precios de reserva, planes de clases y membresías de socios.",
    ) if Rol.PUBLICO in roles else None
    mis_contrataciones = enlace(
        "Mis contrataciones", "membresias:mis_contrataciones", contrataciones_propias_activo,
        "Consultá tus planes y membresías contratados, sus períodos e importes.",
    ) if usuario.esta_habilitado and not administrador else None
    mis_reservas = enlace(
        "Mis reservas", "reservas:mis_reservas", reservas_propias_activo,
        "Consultá las reservas que organizaste.",
    ) if usuario.puede_reservar and not administrador else None
    mis_invitaciones = enlace(
        "Mis invitaciones", "reservas:mis_invitaciones", invitaciones_propias_activo,
        "Consultá las invitaciones a reservas que recibiste.",
    ) if usuario.puede_reservar and not administrador else None
    clases = []
    if administrador:
        clases.append(enlace("Planilla semanal", "clases:planilla", clases_activo, "Programación habitual de clases."))
    elif usuario.esta_habilitado and (
        roles.intersection((Rol.PROFESOR, Rol.ALUMNO))
        or usuario.clases_como_participante.exists() or usuario.asistencias.exists()
    ):
        clases.append(enlace(
            "Mis clases", "clases:actividad_clases", clases_activo,
            "Consulta de tus clases y su historial.", {"usuario_id": usuario.pk},
        ))
    administracion = []
    if usuario.esta_habilitado and usuario.has_perm("usuarios.view_usuario"):
        administracion.append(enlace(
            "Usuarios", "usuarios:usuario_lista", namespace == "usuarios" and not perfil_activo,
            "Alta, consulta y gestión de usuarios, roles y acceso al sistema.",
        ))
    if usuario.esta_habilitado and usuario.has_perm("instalaciones.view_sede"):
        administracion.append(enlace(
            "Instalaciones", "instalaciones:sede_lista", sedes_activo,
            "Consulta y gestión de sedes, canchas, horarios y precios.",
        ))
    catalogo_oferta = None
    if administrador:
        administracion.append(enlace(
            "Contrataciones", "membresias:contratacion_general_lista", contrataciones_admin_activo,
            "Registro y consulta de contrataciones de planes y membresías.",
        ))
        administracion.append(enlace(
            "Horarios especiales", "instalaciones:horarios_especiales", horarios_especiales_activo,
            "Feriados globales y horarios particulares por sede.",
        ))
        catalogo_oferta = enlace(
            "Catálogo", "membresias:plan_lista", catalogo_oferta_activo,
            "Configuración de planes de clases y membresías de socios.",
        )
        administracion.append(catalogo_oferta)
    if administrador:
        administracion.append(enlace("Caja", "caja:caja_actual", namespace == "caja", "Apertura, consulta y cierre de la sesión de caja."))
        administracion.append(enlace(
            "Reportes", "reportes:inicio", namespace == "reportes",
            "Información consolidada de contrataciones, clases, reservas y caja.",
        ))
    auditoria = enlace(
        "Auditoría", "auditoria:auditoria_lista", namespace == "auditoria",
        "Historial de operaciones y consulta de sus valores anteriores y actuales.",
    ) if administrador else None
    modulos_inicio = [{"nombre": "Agenda", "descripcion": agenda["descripcion"], "destino": agenda}] if agenda else []
    modulos_inicio.extend(
        {"nombre": item["nombre"], "descripcion": item["descripcion"], "destino": item}
        for item in administracion if item["destino"] not in ("clases:feriado_lista", "instalaciones:horarios_especiales", "membresias:plan_lista")
    )
    if clases:
        modulos_inicio.append({
            "nombre": "Clases",
            "descripcion": "Programación de clases, asignación de profesores y alumnos, y registro de asistencia.",
            "destino": clases[0], "boton": "Ver planilla semanal" if administrador else "Mi actividad",
        })
    if catalogo_oferta:
        modulos_inicio.append({
            "nombre": catalogo_oferta["nombre"], "descripcion": catalogo_oferta["descripcion"],
            "destino": catalogo_oferta,
            "boton": "Ver catálogo",
        })
    if oferta:
        modulos_inicio.append({
            "nombre": "Oferta de la academia", "descripcion": oferta["descripcion"],
            "destino": oferta, "boton": "Ver oferta",
        })
    if administrador:
        administracion.append(enlace(
            "Envíos de email", "comunicaciones:envios_lista",
            nombre_vista in ("comunicaciones:envios_lista", "comunicaciones:configuracion_notificaciones"),
            "Consulta de entregas y fallos de los emails de la academia.",
        ))
    if auditoria:
        modulos_inicio.append({"nombre": "Auditoría", "descripcion": auditoria["descripcion"], "destino": auditoria})
        administracion.append(auditoria)
    inicio = enlace("Inicio", "inicio", nombre_vista == "inicio", "Inicio de la academia.")
    destinos = [item for item in [inicio, agenda, *clases, mis_reservas, mis_invitaciones, mis_contrataciones, oferta, *administracion] if item]
    seccion_actual = next((item["nombre"] for item in destinos if item["activo"]), "")
    if not seccion_actual:
        if perfil_activo:
            seccion_actual = "Mi perfil"
        elif nombre_vista == "comunicaciones:notificaciones_lista":
            seccion_actual = "Notificaciones"
        elif nombre_vista in ("password_change", "password_change_done"):
            seccion_actual = "Cambiar contraseña"
    grupos = []
    for codigo, titulo in (
        ("actividad", "Actividad" if administrador else "Mi actividad"),
        ("gestion", "Gestión"), ("academia", "Academia"), ("seguimiento", "Seguimiento"),
    ):
        items = [item for item in destinos if item["grupo"] == codigo]
        if items:
            grupos.append({"codigo": codigo, "titulo": titulo, "items": items})
    return {"navegacion_app": {
        "mostrar_notificaciones": usuario.esta_habilitado and not solo_marca,
        "notificaciones_no_leidas": Notificacion.objects.filter(destinatario=usuario, leida=False).count()
            if usuario.esta_habilitado and not solo_marca else 0,
        "mostrar_sidebar": not solo_marca and (usuario.esta_habilitado or Rol.PUBLICO in roles),
        "solo_marca": solo_marca, "grupos": grupos, "seccion_actual": seccion_actual,
        "mostrar_perfil": usuario.esta_habilitado or Rol.PUBLICO in roles,
        "inicio_activo": nombre_vista == "inicio", "agenda": agenda, "oferta": oferta,
        "mis_contrataciones": mis_contrataciones,
        "clases": clases, "clases_activo": clases_activo,
        "administracion": administracion,
        "administracion_activo": any(item["activo"] for item in administracion),
        "perfil_activo": perfil_activo,
        "modulos_inicio": modulos_inicio, "mostrar_preparacion": administrador,
    }}
