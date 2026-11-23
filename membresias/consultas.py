from django.core.paginator import Paginator
from django.db.models import Q

from caja.finanzas import origenes_con_pendiente

from .fechas import meses_contratables
from .models import MembresiaUsuario, PlanUsuario


def contrataciones_con_diferencia_queryset(tipo):
    modelo = PlanUsuario if tipo == "plan" else MembresiaUsuario
    return origenes_con_pendiente(
        modelo.objects.exclude(estado=modelo.Estado.ANULADO), tipo,
    )


def contar_contrataciones_con_diferencia():
    return sum(
        contrataciones_con_diferencia_queryset(tipo).count()
        for tipo in ("plan", "membresia")
    )


def listar_contrataciones_con_diferencia(parametros):
    hay_pendientes = any(
        contrataciones_con_diferencia_queryset(tipo).exists()
        for tipo in ("plan", "membresia")
    )
    busqueda = parametros.get("q", "").strip()[:150]
    tipo_actual = parametros.get("tipo", "")
    if tipo_actual not in ("plan", "membresia"):
        tipo_actual = ""
    estados = (
        (PlanUsuario.Estado.ACTIVO, PlanUsuario.Estado.ACTIVO.label),
        (PlanUsuario.Estado.VENCIDO, PlanUsuario.Estado.VENCIDO.label),
    )
    estado_actual = parametros.get("estado", "")
    if estado_actual not in {valor for valor, _ in estados}:
        estado_actual = ""

    registros = []
    if hay_pendientes:
        tipos = (tipo_actual,) if tipo_actual else ("plan", "membresia")
        for tipo in tipos:
            consulta = contrataciones_con_diferencia_queryset(tipo).select_related("usuario", tipo)
            if busqueda:
                for termino in busqueda.split():
                    consulta = consulta.filter(
                        Q(**{f"{tipo}__nombre__icontains": termino})
                        | Q(usuario__first_name__icontains=termino)
                        | Q(usuario__last_name__icontains=termino)
                        | Q(usuario__username__icontains=termino)
                    )
            if estado_actual:
                consulta = consulta.filter(estado=estado_actual)
            etiqueta_tipo = "Plan" if tipo == "plan" else "Membresía"
            ruta_detalle = f"membresias:contratacion_{tipo}_detalle"
            for contratacion in consulta:
                registros.append({
                    "contratacion": contratacion,
                    "tipo": tipo,
                    "tipo_texto": etiqueta_tipo,
                    "ruta_detalle": ruta_detalle,
                })
        registros.sort(
            key=lambda item: (item["contratacion"].mes_cubierto, item["contratacion"].pk, item["tipo"]),
            reverse=True,
        )
    return {
        "pagina": Paginator(registros, 25).get_page(parametros.get("pagina")),
        "busqueda": busqueda,
        "tipo_actual": tipo_actual,
        "estado_actual": estado_actual,
        "estados": estados,
        "hay_pendientes": hay_pendientes,
    }


def listar_contrataciones(contrataciones, parametros, *, tipo, buscar_usuario=True):
    modelo = contrataciones.model
    hay_contrataciones = contrataciones.exists()
    busqueda = parametros.get("q", "").strip()[:150]
    estado = parametros.get("estado", "")
    mes = parametros.get("mes", "")
    meses = meses_contratables(incluir_mes_siguiente=True)
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
