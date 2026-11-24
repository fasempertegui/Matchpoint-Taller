from django import template

register = template.Library()

ESTADOS = {
    "habilitacion": {
        "activo": ("check", "positivo", "Activo"),
        "activa": ("check", "positivo", "Activa"),
        "inactivo": ("cruz", "neutro", "Inactivo"),
        "inactiva": ("cruz", "neutro", "Inactiva"),
        True: ("check", "positivo", "Activo"),
        False: ("cruz", "neutro", "Inactivo"),
    },
    "contratacion": {
        "activo": ("check", "positivo", "Activo"),
        "vencido": ("reloj", "advertencia", "Vencido"),
        "anulado": ("cruz", "negativo", "Anulado"),
    },
    "envio": {
        "pendiente": ("reloj", "advertencia", "Pendiente"),
        "en_proceso": ("proceso", "proceso", "En proceso"),
        "enviado": ("check", "positivo", "Enviado"),
        "fallido": ("error", "negativo", "Fallido"),
        "descartado": ("descartado", "neutro", "Descartado"),
    },
    "sesion": {
        "abierta": ("abierto", "positivo", "Abierta"),
        "cerrada": ("cerrado", "neutro", "Cerrada"),
    },
    "revision_diferencia": {
        "pendiente": ("reloj", "advertencia", "Pendiente de revisión"),
        "revisada": ("check", "positivo", "Revisada"),
    },
    "movimiento": {
        "vigente": ("check", "positivo", "Vigente"),
        "anulado": ("cruz", "negativo", "Anulado"),
    },
    "evento": {
        "programado": ("calendario", "proceso", "Programado"),
        "en_curso": ("curso", "proceso", "En curso"),
        "finalizado": ("check", "positivo", "Finalizado"),
        "anulado": ("cruz", "negativo", "Anulado"),
    },
    "respuesta": {
        "pendiente": ("reloj", "advertencia", "Pendiente"),
        "afirmativa": ("check", "positivo", "Aceptada"),
        "negativa": ("cruz", "negativo", "Rechazada"),
        "asistira": ("check", "positivo", "Asistirá"),
        "no_asistira": ("cruz", "negativo", "No asistirá"),
    },
    "asistencia": {
        "presente": ("check", "positivo", "Presente"),
        "ausente": ("cruz", "negativo", "Ausente"),
        "sin_registrar": ("pregunta", "advertencia", "Sin registrar"),
    },
}


@register.inclusion_tag("componentes/indicador_estado.html")
def indicador_estado(dominio, estado, texto="", integrado=False):
    datos = ESTADOS.get(dominio, {}).get(estado)
    if datos is None:
        return {"texto": texto or estado}
    figura, color, etiqueta = datos
    return {
        "figura": figura, "color": color, "texto": texto or etiqueta,
        "contexto": (
            "Asistencia" if dominio == "asistencia"
            else "Respuesta" if dominio == "respuesta"
            else "Revisión" if dominio == "revision_diferencia"
            else "Estado"
        ),
        "integrado": integrado,
    }
