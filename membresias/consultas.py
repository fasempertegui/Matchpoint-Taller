from django.core.paginator import Paginator
from django.db.models import Q

from .fechas import meses_contratables


def listar_contrataciones(contrataciones, parametros, *, tipo, buscar_usuario=True):
    modelo = contrataciones.model
    hay_contrataciones = contrataciones.exists()
    busqueda = parametros.get("q", "").strip()[:150]
    estado = parametros.get("estado", "")
    mes = parametros.get("mes", "")
    meses = meses_contratables()
    if busqueda:
        coincidencias = Q(**{f"{tipo}__nombre__icontains": busqueda})
        if buscar_usuario:
            coincidencias |= (
                Q(usuario__first_name__icontains=busqueda) | Q(usuario__last_name__icontains=busqueda)
                | Q(usuario__username__icontains=busqueda)
            )
        contrataciones = contrataciones.filter(coincidencias)
    if estado in modelo.Estado.values:
        contrataciones = contrataciones.filter(estado=estado)
    else:
        estado = ""
    if mes in {fecha.isoformat() for fecha in meses}:
        contrataciones = contrataciones.filter(mes_cubierto=mes)
    else:
        mes = ""
    return {
        "pagina": Paginator(contrataciones, 25).get_page(parametros.get("pagina")),
        "busqueda": busqueda, "estado_actual": estado, "mes_actual": mes,
        "estados": modelo.Estado.choices, "meses": meses, "hay_contrataciones": hay_contrataciones,
    }
