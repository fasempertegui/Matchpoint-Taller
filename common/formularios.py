from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.inclusion_tag("componentes/pasos_formulario.html")
def pasos_formulario(actual, total, nombre="", etiqueta="Progreso del formulario"):
    actual_int = int(actual)
    total_int = int(total)
    return {
        "actual": actual_int,
        "total": total_int,
        "pasos": range(1, total_int + 1),
        "nombre": nombre,
        "etiqueta": etiqueta,
    }


@register.simple_block_tag(takes_context=True)
def modal_formulario(
    context,
    content,
    titulo,
    action="",
    subtitulo="",
    peligro=False,
    amplio=False,
    texto_enviar="Guardar",
    texto_cancelar="Cancelar",
    mostrar_enviar=True,
    clase_enviar="",
    metodo="post",
    id_titulo="modal-formulario-titulo",
):
    if not clase_enviar:
        clase_enviar = "boton-confirmar-peligro" if peligro else "boton-primario"
    return render_to_string(
        "componentes/modal_formulario.html",
        {
            "titulo": titulo,
            "subtitulo": subtitulo,
            "action": action,
            "peligro": bool(peligro),
            "amplio": bool(amplio),
            "texto_enviar": texto_enviar,
            "texto_cancelar": texto_cancelar,
            "mostrar_enviar": bool(mostrar_enviar),
            "clase_enviar": clase_enviar,
            "metodo": metodo,
            "id_titulo": id_titulo,
            "contenido": content,
            "csrf_token": context.get("csrf_token"),
        },
        request=context.get("request"),
    )
