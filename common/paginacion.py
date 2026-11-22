from django import template
from django.http import QueryDict


register = template.Library()


@register.filter
def parametros_paginacion(consulta):
    parametros = QueryDict(consulta or "", mutable=True)
    parametros.pop("pagina", None)
    return parametros.lists()
