from .mensajes import dato_fecha, dato_hora
from .models import EnvioEmail
from .servicios import encolar_email


def _avisar_retirada(actividad, relacion, usuario, funcion, tipo):
    textos = {
        "profesor": "Se retiró tu asignación como profesor de esta clase.",
        "participante": "Se retiró tu participación en esta clase.",
        "invitado": "Se retiró tu invitación a esta reserva.",
    }
    turno = actividad.evento.turno
    return encolar_email(
        clave=f"{tipo}:{funcion}:{relacion.identidad}",
        tipo=tipo,
        destinatario=usuario.email,
        datos={
            "vigencia": {
                "usuario_id": usuario.pk,
                "participacion": {"tipo": funcion, "actividad_id": actividad.pk, "identidad": str(relacion.identidad)},
            },
            "mensaje": {
                "parrafos": [textos[funcion]],
                "datos": [
                    dato_fecha("Fecha", turno.fecha),
                    dato_hora("Inicio", turno.hora_inicio),
                    dato_hora("Fin", turno.hora_fin),
                    {"etiqueta": "Sede", "valor": turno.cancha.sede.nombre},
                    {"etiqueta": "Cancha", "valor": turno.cancha.nombre},
                ],
            },
        },
    )


def avisar_retirada_clase(clase, relacion, funcion):
    usuario = relacion.profesor if funcion == "profesor" else relacion.usuario
    return _avisar_retirada(clase, relacion, usuario, funcion, EnvioEmail.Tipo.RETIRADA_CLASE)


def avisar_retirada_invitacion(reserva, relacion):
    return _avisar_retirada(reserva, relacion, relacion.usuario, "invitado", EnvioEmail.Tipo.RETIRADA_INVITACION)
