from django import template
from django.template.loader import render_to_string

register = template.Library()


@register.simple_block_tag(takes_context=True)
def tarjeta_filtros(context, content, abierto=None):
    if abierto is None:
        parametros = context["request"].GET
        abierto = any(
            valor for clave, valores in parametros.lists() if clave != "pagina" for valor in valores
        )
    return render_to_string(
        "componentes/tarjeta_filtros.html",
        {"contenido": content, "abierto": abierto},
    )
