from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import CharField, F, Q, Value
from django.urls import reverse

from caja.finanzas import anotar_situacion_financiera, origenes_con_pendiente

from .fechas import meses_contratables
from .models import MembresiaUsuario, PlanUsuario

SITUACIONES_COBRO = (
    ("faltante", "Falta cobrar"),
    ("cubierto", "Cubierto"),
    ("excedente", "Excedente por resolver"),
)
CERO = Decimal("0.00")


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


def _filtrar_busqueda_contrataciones(consulta, busqueda, *, tipo, buscar_usuario=True):
    for termino in busqueda.split():
        limpio = termino.lstrip("@") if termino.startswith("@") else termino
        if not limpio:
            continue
        coincidencias = Q(**{f"{tipo}__nombre__icontains": limpio})
        if buscar_usuario:
            coincidencias |= (
                Q(usuario__first_name__icontains=limpio)
                | Q(usuario__last_name__icontains=limpio)
                | Q(usuario__username__icontains=limpio)
            )
        consulta = consulta.filter(coincidencias)
    return consulta


def _aplicar_filtro_cobro(consulta, cobro, modelo):
    if cobro == "faltante":
        return consulta.exclude(estado=modelo.Estado.ANULADO).filter(pendiente_cobro__gt=0)
    if cobro == "cubierto":
        return consulta.exclude(estado=modelo.Estado.ANULADO).filter(pendiente_cobro=0)
    if cobro == "excedente":
        return consulta.exclude(estado=modelo.Estado.ANULADO).filter(pendiente_cobro__lt=0)
    return consulta


def _fila_administracion(
    *, pk, tipo, usuario_nombre, usuario_username, producto_nombre,
    mes_cubierto, importe_financiero, pendiente_cobro, estado,
):
    if estado == PlanUsuario.Estado.ANULADO:
        por_cubrir_tipo = "anulado"
        por_cubrir_monto = None
    elif pendiente_cobro > CERO:
        por_cubrir_tipo = "faltante"
        por_cubrir_monto = pendiente_cobro
    elif pendiente_cobro < CERO:
        por_cubrir_tipo = "excedente"
        por_cubrir_monto = -pendiente_cobro
    else:
        por_cubrir_tipo = "cubierto"
        por_cubrir_monto = CERO
    return {
        "pk": pk,
        "tipo": tipo,
        "tipo_texto": "Plan" if tipo == "plan" else "Membresía",
        "usuario_nombre": usuario_nombre,
        "usuario_username": usuario_username,
        "producto_nombre": producto_nombre,
        "mes_cubierto": mes_cubierto,
        "importe_financiero": importe_financiero,
        "pendiente_cobro": pendiente_cobro,
        "por_cubrir_tipo": por_cubrir_tipo,
        "por_cubrir_monto": por_cubrir_monto,
        "estado": estado,
        "url_detalle": reverse(f"membresias:contratacion_{tipo}_detalle", args=[pk]),
    }


def _consulta_administracion(tipo, *, busqueda, estado, mes, cobro):
    modelo = PlanUsuario if tipo == "plan" else MembresiaUsuario
    consulta = modelo.objects.all()
    if busqueda:
        consulta = _filtrar_busqueda_contrataciones(consulta, busqueda, tipo=tipo, buscar_usuario=True)
    if estado:
        consulta = consulta.filter(estado=estado)
    if mes:
        consulta = consulta.filter(mes_cubierto=mes)
    consulta = anotar_situacion_financiera(consulta, tipo)
    return _aplicar_filtro_cobro(consulta, cobro, modelo)


def listar_contrataciones_administracion(parametros, *, tipo="todas"):
    meses = meses_contratables(incluir_mes_siguiente=True)
    busqueda = parametros.get("q", "").strip()[:150]
    estado = parametros.get("estado", "")
    if estado not in PlanUsuario.Estado.values:
        estado = ""
    mes = parametros.get("mes", "")
    if mes not in {fecha.isoformat() for fecha in meses}:
        mes = ""
    cobro = parametros.get("cobro", "")
    if cobro not in {valor for valor, _ in SITUACIONES_COBRO}:
        cobro = ""

    if tipo == "todas":
        hay_contrataciones = PlanUsuario.objects.exists() or MembresiaUsuario.objects.exists()
        proyecciones = []
        for subtipo in ("plan", "membresia"):
            consulta = _consulta_administracion(subtipo, busqueda=busqueda, estado=estado, mes=mes, cobro=cobro)
            proyecciones.append(
                consulta.annotate(
                    tipo_registro=Value(subtipo, output_field=CharField()),
                    producto_nombre=F(f"{subtipo}__nombre"),
                ).values(
                    "id",
                    "tipo_registro",
                    "usuario__first_name",
                    "usuario__last_name",
                    "usuario__username",
                    "producto_nombre",
                    "mes_cubierto",
                    "importe_financiero",
                    "pendiente_cobro",
                    "estado",
                ).order_by()
            )
        combinada = proyecciones[0].union(proyecciones[1], all=True).order_by("-mes_cubierto", "-id", "tipo_registro")
        pagina = Paginator(combinada, 25).get_page(parametros.get("pagina"))
        filas = [
            _fila_administracion(
                pk=item["id"],
                tipo=item["tipo_registro"],
                usuario_nombre=f"{item['usuario__first_name']} {item['usuario__last_name']}".strip() or item["usuario__username"],
                usuario_username=item["usuario__username"],
                producto_nombre=item["producto_nombre"],
                mes_cubierto=item["mes_cubierto"],
                importe_financiero=item["importe_financiero"],
                pendiente_cobro=item["pendiente_cobro"],
                estado=item["estado"],
            )
            for item in pagina
        ]
    else:
        modelo = PlanUsuario if tipo == "plan" else MembresiaUsuario
        hay_contrataciones = modelo.objects.exists()
        consulta = _consulta_administracion(
            tipo, busqueda=busqueda, estado=estado, mes=mes, cobro=cobro,
        ).select_related("usuario", tipo).order_by("-mes_cubierto", "-pk")
        pagina = Paginator(consulta, 25).get_page(parametros.get("pagina"))
        filas = [
            _fila_administracion(
                pk=contrato.pk,
                tipo=tipo,
                usuario_nombre=str(contrato.usuario),
                usuario_username=contrato.usuario.username,
                producto_nombre=contrato.producto.nombre,
                mes_cubierto=contrato.mes_cubierto,
                importe_financiero=contrato.importe_financiero,
                pendiente_cobro=contrato.pendiente_cobro,
                estado=contrato.estado,
            )
            for contrato in pagina
        ]

    return {
        "pagina": pagina,
        "filas": filas,
        "busqueda": busqueda,
        "estado_actual": estado,
        "mes_actual": mes,
        "cobro_actual": cobro,
        "estados": PlanUsuario.Estado.choices,
        "situaciones_cobro": SITUACIONES_COBRO,
        "meses": meses,
        "hay_contrataciones": hay_contrataciones,
    }


def listar_contrataciones(contrataciones, parametros, *, tipo, buscar_usuario=True):
    modelo = contrataciones.model
    hay_contrataciones = contrataciones.exists()
    busqueda = parametros.get("q", "").strip()[:150]
    estado = parametros.get("estado", "")
    mes = parametros.get("mes", "")
    meses = meses_contratables(incluir_mes_siguiente=True)
    if busqueda:
        contrataciones = _filtrar_busqueda_contrataciones(
            contrataciones, busqueda, tipo=tipo, buscar_usuario=buscar_usuario,
        )
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
