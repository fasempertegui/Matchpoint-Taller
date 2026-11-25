from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_block_tag
def pestanas(content, etiqueta, clases="", modo="navegacion", resultados_filtros=""):
    return render_to_string("componentes/pestanas.html", {
        "contenido": content,
        "etiqueta": etiqueta,
        "clases": clases,
        "es_tablist": modo == "paneles",
        "resultados_filtros": resultados_filtros,
    })
