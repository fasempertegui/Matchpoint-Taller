from datetime import datetime, timedelta
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

from .mensajes import dato_fecha, dato_hora
from .servicios import encolar_email


def datos_turno(actividad):
    turno = actividad.evento.turno
    return [dato_fecha("Fecha", turno.fecha), dato_hora("Inicio", turno.hora_inicio),
            dato_hora("Fin", turno.hora_fin), {"etiqueta": "Sede", "valor": turno.cancha.sede.nombre},
            {"etiqueta": "Cancha", "valor": turno.cancha.nombre}]


def dentro_de_una_hora(actividad):
    turno = actividad.evento.turno
    inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
    return timezone.now() < inicio <= timezone.now() + timedelta(hours=1)


def participacion(relacion, funcion):
    return {"tipo": funcion, "actividad_id": relacion.reserva_id if funcion == "invitado" else relacion.clase_id,
            "identidad": str(relacion.identidad)}


def avisar_reserva(reserva, tipo, *, invitado=None, respuesta=None):
    usuario = invitado.usuario if invitado is not None else reserva.organizador
    textos = {
        "reserva_creada": "Tu reserva fue confirmada.",
        "invitacion": "Te invitaron a participar en esta reserva. Ingresá para responder.",
        "reserva_anulada": "La reserva en la que participabas como invitado fue anulada." if invitado else "Tu reserva fue anulada. Consultá el motivo en el detalle.",
        "respuesta_invitacion": f"{respuesta.usuario}: {respuesta.get_respuesta_display()}." if respuesta else "",
    }
    identidad = str(invitado.identidad) if invitado else "organizador"
    if respuesta is not None:
        identidad = f"{respuesta.identidad}:{uuid4()}"
    vigencia = {"usuario_id": usuario.pk, "evento_id": reserva.evento_id, "reserva_id": reserva.pk}
    if invitado is not None:
        vigencia["participacion"] = participacion(invitado, "invitado")
    if tipo in ("reserva_creada", "invitacion"):
        vigencia["cubre_recordatorio"] = dentro_de_una_hora(reserva)
    return encolar_email(
        clave=f"{tipo}:{reserva.pk}:{identidad}", tipo=tipo, destinatario=usuario.email,
        datos={"vigencia": vigencia, "mensaje": {"parrafos": [textos[tipo]], "datos": datos_turno(reserva),
               "acciones": [{"texto": "Ver reserva", "ruta": reverse("reservas:reserva_detalle", args=[reserva.pk])}]}},
    )


def avisar_clase(clase, tipo, relacion, funcion, *, alumno=None):
    usuario = relacion.profesor if funcion == "profesor" else relacion.usuario
    textos = {
        "asignacion_clase": "Se te asignó como profesor de esta clase." if funcion == "profesor" else "Tu clase comienza dentro de una hora.",
        "cancha_cambiada": "La clase cambió de cancha. Consultá la nueva ubicación.",
        "clase_anulada": "La clase fue anulada. Consultá el motivo en el detalle.",
        "no_asisto": f"{alumno.usuario} avisó que no asistirá a esta clase." if alumno else "",
    }
    transicion = str(uuid4()) if tipo == "cancha_cambiada" else clase.evento.actualizado_en.isoformat()
    if tipo == "asignacion_clase":
        transicion = "alta"
    elif alumno is not None:
        transicion = str(alumno.identidad)
    vigencia = {"usuario_id": usuario.pk, "evento_id": clase.evento_id, "participacion": participacion(relacion, funcion)}
    if tipo == "asignacion_clase":
        vigencia["cubre_recordatorio"] = dentro_de_una_hora(clase)
    return encolar_email(
        clave=f"{tipo}:{funcion}:{relacion.identidad}:{transicion}", tipo=tipo, destinatario=usuario.email,
        datos={"vigencia": vigencia, "mensaje": {"parrafos": [textos[tipo]], "datos": datos_turno(clase),
               "acciones": [{"texto": "Ver clase", "ruta": reverse("clases:clase_detalle", args=[clase.pk])}]}},
    )


def avisar_asignaciones(clase, profesores_ids=None, participantes_ids=None):
    profesores = clase.profesores.select_related("profesor")
    participantes = clase.alumnos.select_related("usuario")
    if profesores_ids is not None:
        profesores = profesores.filter(profesor_id__in=profesores_ids)
    if participantes_ids is not None:
        participantes = participantes.filter(usuario_id__in=participantes_ids)
    for relacion in profesores:
        avisar_clase(clase, "asignacion_clase", relacion, "profesor")
    if dentro_de_una_hora(clase):
        for relacion in participantes.filter(respuesta="asistira"):
            avisar_clase(clase, "asignacion_clase", relacion, "participante")


def avisar_anulacion_clase(clase):
    for relacion in clase.profesores.select_related("profesor"):
        avisar_clase(clase, "clase_anulada", relacion, "profesor")
    for relacion in clase.alumnos.select_related("usuario"):
        avisar_clase(clase, "clase_anulada", relacion, "participante")


def avisar_generacion(clases):
    corrida = uuid4()
    grupos = {}
    for clase in clases:
        for relacion in clase.profesores.select_related("profesor"):
            grupo = grupos.setdefault(relacion.profesor_id, {"usuario": relacion.profesor, "referencias": [], "apartados": []})
            grupo["referencias"].append({"clase_id": clase.pk, "identidad": str(relacion.identidad), "cubre_recordatorio": dentro_de_una_hora(clase)})
            grupo["apartados"].append({"titulo": "Clase programada", "datos": datos_turno(clase),
                                      "acciones": [{"texto": "Ver clase", "ruta": reverse("clases:clase_detalle", args=[clase.pk])}]})
        avisar_asignaciones(clase, profesores_ids=())
    for grupo in grupos.values():
        usuario = grupo["usuario"]
        encolar_email(clave=f"generacion:{corrida}:{usuario.pk}", tipo="generacion_clases", destinatario=usuario.email,
                      datos={"vigencia": {"usuario_id": usuario.pk, "clases_generadas": grupo["referencias"]},
                             "mensaje": {"parrafos": ["Estas son tus clases programadas como profesor."], "apartados": grupo["apartados"]}})
