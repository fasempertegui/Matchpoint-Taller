from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_block_tag
def tabla(content, clases="", centrada=True, listado=True):
    return render_to_string("componentes/tabla.html", {
        "contenido": content,
        "clases": clases,
        "centrada": centrada,
        "listado": listado,
    })


@register.simple_block_tag
def tabla_datos(content, clases="", etiqueta="", etiqueta_por=""):
    return render_to_string("componentes/tabla_datos.html", {
        "contenido": content,
        "clases": clases,
        "etiqueta": etiqueta,
        "etiqueta_por": etiqueta_por,
    })
