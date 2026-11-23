from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from caja.models import SesionCaja
from clases.consultas import clases_sin_asistencia_queryset
from comunicaciones.models import EnvioEmail
from instalaciones.models import Cancha, Sede, SedeHorario
from membresias.consultas import contar_contrataciones_con_diferencia
from membresias.continuidad import ventana_continuidad
from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.models import Evento
from reservas.servicios import reservas_sin_resultado_queryset
from usuarios.models import Usuario

MESES_NOMBRES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
MESES_CORTOS = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)
DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def _restar_meses(mes_inicio, cantidad):
    total = mes_inicio.year * 12 + (mes_inicio.month - 1) - cantidad
    anio, indice_mes = divmod(total, 12)
    return mes_inicio.replace(year=anio, month=indice_mes + 1, day=1)


def _curva_suave(puntos, y_min, y_max):
    def limitar(valor):
        return max(y_min, min(y_max, valor))

    trazo = [f"M{puntos[0][0]:.1f},{puntos[0][1]:.1f}"]
    ultimo = len(puntos) - 1
    for i in range(ultimo):
        p0 = puntos[max(0, i - 1)]
        p1 = puntos[i]
        p2 = puntos[i + 1]
        p3 = puntos[min(ultimo, i + 2)]
        cp1x = p1[0] + (p2[0] - p0[0]) / 6
        cp1y = limitar(p1[1] + (p2[1] - p0[1]) / 6)
        cp2x = p2[0] - (p3[0] - p1[0]) / 6
        cp2y = limitar(p2[1] - (p3[1] - p1[1]) / 6)
        trazo.append(f"C{cp1x:.1f},{cp1y:.1f} {cp2x:.1f},{cp2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(trazo)


def _construir_sparkline(serie, unidad):
    ancho = 360.0
    alto = 72.0
    pad_sup = 12.0
    pad_inf = 10.0
    pad_der = 14.0
    valores = [item["valor"] for item in serie]
    min_v = min(valores)
    max_v = max(valores)
    rango = max(max_v - min_v, 1)
    cantidad = len(serie)
    divisor = max(cantidad - 1, 1)

    puntos = [
        (
            (indice / divisor) * (ancho - pad_der),
            alto - pad_inf - ((item["valor"] - min_v) / rango) * (alto - pad_sup - pad_inf),
        )
        for indice, item in enumerate(serie)
    ]
    ultimo_x, ultimo_y = puntos[-1]
    curva = _curva_suave(puntos, 5.0, alto - 5.0)
    linea_d = f"{curva} L{ancho:.1f},{ultimo_y:.1f}"
    area_d = f"{linea_d} L{ancho:.1f},{alto:.1f} L0,{alto:.1f} Z"

    zonas = []
    for indice, (item, (cx, cy)) in enumerate(zip(serie, puntos)):
        inicio_zona = round((puntos[indice - 1][0] + cx) / 2, 2) if indice > 0 else 0
        fin_zona = round((cx + puntos[indice + 1][0]) / 2, 2) if indice < cantidad - 1 else ancho
        zonas.append({
            "x": f"{inicio_zona:.2f}",
            "ancho": f"{fin_zona - inicio_zona:.2f}",
            "cx": f"{cx:.1f}",
            "cy": f"{cy:.1f}",
            "es_ultimo": indice == cantidad - 1,
            "tooltip": f"{item['etiqueta']}: {item['valor']} {unidad}",
        })

    return {
        "linea_d": linea_d,
        "area_d": area_d,
        "ultimo_x": f"{ultimo_x:.1f}",
        "ultimo_y": f"{ultimo_y:.1f}",
        "zonas": zonas,
    }


def _datos_variacion(actual, anterior):
    delta = actual - anterior
    if delta > 0:
        return {"texto": f"+{delta}", "clase": "sube"}
    if delta < 0:
        return {"texto": str(delta), "clase": "baja"}
    return {"texto": "0", "clase": "igual"}


def _serie_mensual_contratos(modelo, meses, mes_actual):
    filas = (
        modelo.objects.filter(mes_cubierto__in=meses)
        .filter(
            Q(mes_cubierto=mes_actual, estado=modelo.Estado.ACTIVO)
            | (Q(mes_cubierto__lt=mes_actual) & ~Q(estado=modelo.Estado.ANULADO))
        )
        .values("mes_cubierto")
        .annotate(cantidad=Count("usuario_id", distinct=True))
    )
    por_mes = {fila["mes_cubierto"]: fila["cantidad"] for fila in filas}
    return [
        {"etiqueta": MESES_NOMBRES[mes.month - 1], "valor": por_mes.get(mes, 0)}
        for mes in meses
    ]


def _serie_usuarios_30_dias(hoy, tz):
    inicio_dia = hoy - timedelta(days=29)
    inicio_dt = timezone.make_aware(datetime.combine(inicio_dia, time.min), tz)
    fin_dt = timezone.make_aware(datetime.combine(hoy + timedelta(days=1), time.min), tz)

    base = Usuario.objects.filter(date_joined__lt=inicio_dt).count()
    altas_por_dia = {
        fila["dia"]: fila["cantidad"]
        for fila in (
            Usuario.objects.filter(date_joined__gte=inicio_dt, date_joined__lt=fin_dt)
            .annotate(dia=TruncDate("date_joined", tzinfo=tz))
            .values("dia")
            .annotate(cantidad=Count("pk"))
        )
    }

    acumulado = base
    serie = []
    for desplazamiento in range(30):
        dia = inicio_dia + timedelta(days=desplazamiento)
        acumulado += altas_por_dia.get(dia, 0)
        serie.append({
            "etiqueta": f"{dia.day} {MESES_CORTOS[dia.month - 1]}",
            "valor": acumulado,
        })
    return serie


def _contexto_actividad_hoy(hoy, hora_actual):
    eventos_hoy = (
        Evento.objects.filter(
            tipo__in=(Evento.Tipo.CLASE, Evento.Tipo.RESERVA),
            turno__fecha=hoy,
        )
        .exclude(estado=Evento.Estado.ANULADO)
        .values("turno__hora_inicio", "tipo")
        .annotate(cantidad=Count("pk"))
    )
    conteo_por_hora = {}
    clases_hoy = 0
    reservas_hoy = 0
    for fila in eventos_hoy:
        hora = fila["turno__hora_inicio"].hour
        cantidad = fila["cantidad"]
        par = conteo_por_hora.setdefault(hora, {"clases": 0, "reservas": 0})
        if fila["tipo"] == Evento.Tipo.CLASE:
            par["clases"] += cantidad
            clases_hoy += cantidad
        else:
            par["reservas"] += cantidad
            reservas_hoy += cantidad

    hora_inicio = min([7, *conteo_por_hora.keys()])
    hora_fin = max([22, *conteo_por_hora.keys()])
    horas_rango = list(range(hora_inicio, hora_fin + 1))

    max_serie = max(
        (max(par["clases"], par["reservas"]) for par in conteo_por_hora.values()),
        default=0,
    )
    max_eje = max(max_serie, 1)
    paso_y = 1 if max_eje <= 5 else (max_eje + 4) // 5
    y_max = ((max_eje + paso_y - 1) // paso_y) * paso_y
    guias_y = [
        {"valor": valor, "bottom": f"{(valor / y_max) * 100:.4f}%"}
        for valor in range(0, y_max + 1, paso_y)
    ]

    horas_hoy = []
    total_horas = len(horas_rango)
    for indice, hora in enumerate(horas_rango):
        par = conteo_por_hora.get(hora, {"clases": 0, "reservas": 0})
        clases_h = par["clases"]
        reservas_h = par["reservas"]
        total_h = clases_h + reservas_h
        mostrar_etiqueta = (indice % 3 == 0) or (indice == total_horas - 1)
        hora_txt = f"{hora:02d}:00"
        horas_hoy.append({
            "hora": hora,
            "etiqueta": f"{hora:02d}h" if mostrar_etiqueta else "",
            "clases": clases_h,
            "reservas": reservas_h,
            "total": total_h,
            "es_actual": hora == hora_actual,
            "alto_clases": f"{(clases_h / y_max) * 100:.4f}%" if clases_h else "0%",
            "alto_reservas": f"{(reservas_h / y_max) * 100:.4f}%" if reservas_h else "0%",
            "tooltip_clases": f"{hora_txt} · {clases_h} {'clase' if clases_h == 1 else 'clases'}" if clases_h else "",
            "tooltip_reservas": f"{hora_txt} · {reservas_h} {'reserva' if reservas_h == 1 else 'reservas'}" if reservas_h else "",
            "tooltip_vacio": f"{hora_txt} · Sin turnos",
        })

    return {
        "hoy": clases_hoy + reservas_hoy,
        "clases": clases_hoy,
        "reservas": reservas_hoy,
        "horas": horas_hoy,
        "cantidad_horas": total_horas,
        "guias_y": guias_y,
    }


def _contexto_para_revisar():
    clases_sin_asistencia = clases_sin_asistencia_queryset().count()
    reservas_sin_resultado = reservas_sin_resultado_queryset().count()
    contrataciones_diferencia = contar_contrataciones_con_diferencia()
    emails_fallidos = EnvioEmail.objects.filter(estado=EnvioEmail.Estado.FALLIDO).count()

    filas = [
        {
            "texto": "Clases finalizadas sin asistencia cargada",
            "cantidad": clases_sin_asistencia,
            "badge_clase": "baja" if clases_sin_asistencia else "igual",
            "enlace_texto": "Ver clases",
            "url": reverse("clases:sin_asistencia"),
        },
        {
            "texto": "Reservas finalizadas sin resultado",
            "cantidad": reservas_sin_resultado,
            "badge_clase": "baja" if reservas_sin_resultado else "igual",
            "enlace_texto": "Ver reservas",
            "url": reverse("reservas:sin_resultado"),
        },
        {
            "texto": "Contrataciones con diferencia por cubrir",
            "cantidad": contrataciones_diferencia,
            "badge_clase": "info" if contrataciones_diferencia else "igual",
            "enlace_texto": "Ver contrataciones",
            "url": reverse("membresias:contrataciones_por_cubrir"),
        },
        {
            "texto": "Emails fallidos",
            "cantidad": emails_fallidos,
            "badge_clase": "baja" if emails_fallidos else "igual",
            "enlace_texto": "Ver envíos",
            "url": f"{reverse('comunicaciones:envios_lista')}?estado=fallido",
        },
    ]
    todo_al_dia = all(fila["cantidad"] == 0 for fila in filas)
    return {"filas": filas, "todo_al_dia": todo_al_dia}


def _horas_abiertas_horario(horario):
    horas = set(range(horario.hora_inicio_1.hour, horario.hora_fin_1.hour))
    if horario.hora_inicio_2 is not None and horario.hora_fin_2 is not None:
        horas.update(range(horario.hora_inicio_2.hour, horario.hora_fin_2.hour))
    return horas


def _contexto_ocupacion(hoy):
    # Últimas 4 semanas completas (28 días previos a hoy, 4 ocurrencias por cada día de semana).
    desde = hoy - timedelta(days=28)
    hasta = hoy - timedelta(days=1)
    sedes = list(Sede.objects.filter(estado=Sede.Estado.ACTIVA).order_by("nombre"))
    canchas_por_sede = dict(
        Cancha.objects.filter(sede__in=sedes, estado=Cancha.Estado.ACTIVA)
        .values("sede_id")
        .annotate(total=Count("pk"))
        .values_list("sede_id", "total")
    )

    horarios_por_sede = {sede.pk: {} for sede in sedes}
    horas_visibles = set()
    for horario in SedeHorario.objects.filter(sede__in=sedes):
        abiertas = _horas_abiertas_horario(horario)
        horarios_por_sede[horario.sede_id][horario.dia_semana] = abiertas
        horas_visibles.update(abiertas)

    hora_min = min(horas_visibles) if horas_visibles else 7
    hora_max = max(horas_visibles) if horas_visibles else 22
    horas_lista = list(range(hora_min, hora_max + 1))

    eventos_qs = (
        Evento.objects.filter(
            turno__fecha__range=(desde, hasta),
            turno__cancha__sede__in=sedes,
            tipo__in=(Evento.Tipo.CLASE, Evento.Tipo.RESERVA, Evento.Tipo.BLOQUEO),
        )
        .exclude(estado=Evento.Estado.ANULADO)
        .values("turno__cancha__sede_id", "turno__fecha", "turno__hora_inicio", "tipo")
    )
    conteo = {}
    for fila in eventos_qs:
        clave = (fila["turno__cancha__sede_id"], fila["turno__fecha"].isoweekday(), fila["turno__hora_inicio"].hour)
        bucket = conteo.setdefault(clave, {"clases": 0, "reservas": 0, "bloq": 0})
        if fila["tipo"] == Evento.Tipo.CLASE:
            bucket["clases"] += 1
        elif fila["tipo"] == Evento.Tipo.RESERVA:
            bucket["reservas"] += 1
        else:
            bucket["bloq"] += 1

    matrices = {}
    for sede in sedes:
        n_canchas = canchas_por_sede.get(sede.pk, 0)
        horarios_sede = horarios_por_sede[sede.pk]
        matriz = []
        for dia in range(1, 8):
            abiertas = horarios_sede.get(dia, set())
            fila_celdas = []
            for hora in horas_lista:
                if hora not in abiertas or n_canchas == 0:
                    fila_celdas.append({"cerrada": True})
                    continue
                bucket = conteo.get((sede.pk, dia, hora), {"clases": 0, "reservas": 0, "bloq": 0})
                capacidad = 4 * n_canchas
                disp = max(0, capacidad - bucket["bloq"])
                fila_celdas.append({
                    "cerrada": False,
                    "disp": disp,
                    "clases": bucket["clases"],
                    "reservas": bucket["reservas"],
                    "bloq": bucket["bloq"],
                })
            matriz.append(fila_celdas)
        matrices[str(sede.pk)] = matriz

    # Agregado de todas las sedes activas
    matriz_todas = []
    for d_idx in range(7):
        fila_todas = []
        for h_idx in range(len(horas_lista)):
            celdas = [matrices[str(s.pk)][d_idx][h_idx] for s in sedes if not matrices[str(s.pk)][d_idx][h_idx]["cerrada"]]
            if not celdas:
                fila_todas.append({"cerrada": True})
            else:
                fila_todas.append({
                    "cerrada": False,
                    "disp": sum(c["disp"] for c in celdas),
                    "clases": sum(c["clases"] for c in celdas),
                    "reservas": sum(c["reservas"] for c in celdas),
                    "bloq": sum(c["bloq"] for c in celdas),
                })
        matriz_todas.append(fila_todas)
    matrices["todas"] = matriz_todas

    return {
        "sedes": [{"id": str(sede.pk), "nombre": sede.nombre} for sede in sedes],
        "datos_json": {
            "dias": list(DIAS_CORTOS),
            "horas": horas_lista,
            "dia_actual": hoy.isoweekday() - 1,
            "matrices": matrices,
        },
    }


def contexto_inicio_administracion(usuario):
    ahora = timezone.localtime()
    hoy = ahora.date()
    tz = timezone.get_current_timezone()
    mes_actual = hoy.replace(day=1)
    meses_6 = [_restar_meses(mes_actual, n) for n in range(5, -1, -1)]

    apertura, _ = ventana_continuidad(mes_actual)
    encuestas_abiertas = ahora >= apertura
    if ahora < apertura:
        _, cierre_anterior = ventana_continuidad(mes_actual - timedelta(days=1))
        if ahora < cierre_anterior:
            encuestas_abiertas = True

    inicio_hoy = timezone.make_aware(datetime.combine(hoy, time.min), tz)
    fin_hoy = timezone.make_aware(datetime.combine(hoy + timedelta(days=1), time.min), tz)
    usuarios_totales = Usuario.objects.aggregate(
        total=Count("pk"),
        nuevos_hoy=Count("pk", filter=Q(date_joined__gte=inicio_hoy, date_joined__lt=fin_hoy)),
    )
    serie_usuarios = _serie_usuarios_30_dias(hoy, tz)
    nuevos_hoy = usuarios_totales["nuevos_hoy"]

    serie_socios = _serie_mensual_contratos(MembresiaUsuario, meses_6, mes_actual)
    socios_actual = serie_socios[-1]["valor"]
    socios_variacion = _datos_variacion(socios_actual, serie_socios[-2]["valor"])

    serie_planes = _serie_mensual_contratos(PlanUsuario, meses_6, mes_actual)
    planes_actual = serie_planes[-1]["valor"]
    planes_variacion = _datos_variacion(planes_actual, serie_planes[-2]["valor"])

    return {
        "hoy": hoy,
        "mes_actual": mes_actual,
        "actividad": _contexto_actividad_hoy(hoy, ahora.hour),
        "encuestas": {"abiertas": encuestas_abiertas},
        "caja_abierta": (
            SesionCaja.objects.filter(estado=SesionCaja.Estado.ABIERTA).exists()
            if usuario.esta_habilitado and not usuario.debe_cambiar_contrasena
            else None
        ),
        "usuarios": {
            "total": usuarios_totales["total"],
            "nuevos_hoy": nuevos_hoy,
            "badge_texto": f"+{nuevos_hoy} hoy" if nuevos_hoy else "0 hoy",
            "badge_clase": "sube" if nuevos_hoy else "igual",
            "sparkline": _construir_sparkline(serie_usuarios, "usuarios"),
        },
        "socios": {
            "actual": socios_actual,
            "variacion": socios_variacion,
            "sparkline": _construir_sparkline(serie_socios, "socios"),
        },
        "planes": {
            "actual": planes_actual,
            "variacion": planes_variacion,
            "sparkline": _construir_sparkline(serie_planes, "alumnos"),
        },
        "para_revisar": _contexto_para_revisar(),
        "ocupacion": _contexto_ocupacion(hoy),
    }
