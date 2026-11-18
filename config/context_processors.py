from django.urls import reverse

from comunicaciones.models import Notificacion
from usuarios.models import Rol


DESTINOS_NAVEGACION = {
    "inicio": ("casa", "actividad"),
    "agenda:agenda": ("calendario", "actividad"),
    "clases:planilla": ("planilla", "actividad"),
    "clases:actividad_clases": ("pelota", "actividad"),
    "reservas:mis_reservas": ("calendario", "actividad"),
    "membresias:mis_contrataciones": ("cartera", "actividad"),
    "usuarios:usuario_lista": ("usuarios", "gestion"),
    "membresias:catalogos": ("libro", "gestion"),
    "caja:caja_actual": ("cartera", "gestion"),
    "reportes:inicio": ("auditoria", "seguimiento"),
    "instalaciones:sede_lista": ("ubicacion", "academia"),
    "clases:feriado_lista": ("calendario", "academia"),
    "oferta:inicio": ("libro", "academia"),
    "comunicaciones:envios_lista": ("correo", "seguimiento"),
    "comunicaciones:configuracion_notificaciones": ("correo", "seguimiento"),
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
    planilla_activa = namespace == "clases" and ruta.url_name.startswith(("planilla", "generacion_"))
    clases_concretas = namespace == "clases" and not feriados_activo and not planilla_activa
    clases_activo = planilla_activa if administrador else clases_concretas
    reservas_propias_activo = not administrador and namespace == "reservas" and ruta.url_name in (
        "mis_reservas", "reserva_detalle", "reserva_comprobante", "reserva_anular",
        "reserva_invitados", "reserva_socios", "reserva_responder", "reserva_resultado",
    )
    agenda_activa = (namespace in ("agenda", "reservas") and not reservas_propias_activo) or (administrador and clases_concretas)
    perfil_activo = namespace == "usuarios" and ruta.kwargs.get("pk") == usuario.pk
    contrataciones_propias_activo = namespace == "membresias" and ruta.url_name in (
        "mis_contrataciones", "mi_plan_contratado", "mi_membresia_contratado",
        "mi_plan_comprobante", "mi_membresia_comprobante", "mi_plan_continuidad", "mi_membresia_continuidad",
        "mi_membresia_uso",
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
        "Consultá tus reservas e invitaciones.",
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
            "Sedes y canchas", "instalaciones:sede_lista", namespace == "instalaciones",
            "Consulta y gestión de sedes, canchas, horarios y precios.",
        ))
    membresias = None
    if administrador:
        membresias = enlace(
            "Planes y membresías", "membresias:catalogos",
            namespace == "membresias" and not ruta.url_name.startswith("oferta") and not contrataciones_propias_activo,
            "Planes, membresías de socios y contrataciones.",
        )
        administracion.append(membresias)
        administracion.append(enlace(
            "Feriados", "clases:feriado_lista", feriados_activo,
            "Consulta y gestión de feriados.",
        ))
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
        for item in administracion if item["destino"] not in ("clases:feriado_lista", "membresias:catalogos")
    )
    if clases:
        modulos_inicio.append({
            "nombre": "Clases",
            "descripcion": "Programación de clases, asignación de profesores y alumnos, y registro de asistencia.",
            "destino": clases[0], "boton": "Ver planilla semanal" if administrador else "Mi actividad",
        })
    if membresias:
        modulos_inicio.append({
            "nombre": membresias["nombre"], "descripcion": membresias["descripcion"],
            "destino": membresias,
            "boton": "Ver membresías",
        })
    if oferta:
        modulos_inicio.append({
            "nombre": "Oferta de la academia", "descripcion": oferta["descripcion"],
            "destino": oferta, "boton": "Ver oferta",
        })
    if administrador:
        administracion.append(enlace(
            "Envíos de email", "comunicaciones:envios_lista", nombre_vista == "comunicaciones:envios_lista",
            "Consulta de entregas y fallos de los emails de la academia.",
        ))
        administracion.append(enlace(
            "Reglas de notificación", "comunicaciones:configuracion_notificaciones",
            nombre_vista == "comunicaciones:configuracion_notificaciones",
            "Anticipación de recordatorios y calendario de continuidad.",
        ))
    if auditoria:
        modulos_inicio.append({"nombre": "Auditoría", "descripcion": auditoria["descripcion"], "destino": auditoria})
        administracion.append(auditoria)
    inicio = enlace("Inicio", "inicio", nombre_vista == "inicio", "Inicio de la academia.")
    destinos = [item for item in [inicio, agenda, *clases, mis_reservas, mis_contrataciones, oferta, *administracion] if item]
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
        "solo_marca": solo_marca, "grupos": grupos,
        "mostrar_perfil": usuario.esta_habilitado or Rol.PUBLICO in roles,
        "inicio_activo": nombre_vista == "inicio", "agenda": agenda, "oferta": oferta,
        "mis_contrataciones": mis_contrataciones,
        "clases": clases, "clases_activo": clases_activo,
        "administracion": administracion,
        "administracion_activo": any(item["activo"] for item in administracion),
        "perfil_activo": perfil_activo,
        "modulos_inicio": modulos_inicio, "mostrar_preparacion": administrador,
    }}
