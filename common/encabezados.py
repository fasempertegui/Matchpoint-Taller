from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_block_tag
def tarjeta_titulo(content, titulo, subtitulo="", descripcion="", region="", ayuda=""):
    return render_to_string("componentes/tarjeta_titulo.html", {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "descripcion": descripcion,
        "ayuda": ayuda,
        "acciones": content if content.strip() else "",
        "region": region,
    })


@register.simple_block_tag
def texto_titulo(content):
    return content
