from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from clases.consultas import (
    ETIQUETAS_CONTINUIDAD_CORTAS,
    clases_sin_asistencia_profesor_queryset,
    resumen_clases_mes,
)
from clases.models import Clase, ClaseAlumno
from membresias.continuidad import contexto_continuidad
from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.horas import resumen_horas_del_mes
from reservas.models import Evento, Reserva, ReservaInvitado
from reservas.servicios import invitaciones_por_responder
from usuarios.models import Rol

DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
MESES_NOMBRES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
MESES_CORTOS = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)


def _referencia_fecha(fecha, hoy):
    if fecha == hoy:
        return "Hoy"
    if fecha == hoy + timedelta(days=1):
        return "Mañana"
    return f"{DIAS_CORTOS[fecha.isoweekday() - 1]} {fecha.day} {MESES_CORTOS[fecha.month - 1]}"


def _proximas_actividades(usuario, ahora):
    hoy = ahora.date()
    futuras = Q(evento__turno__fecha__gt=hoy) | Q(
        evento__turno__fecha=hoy, evento__turno__hora_inicio__gt=ahora.time(),
    )
    clases = list(
        Clase.objects.filter(
            Q(profesores__profesor=usuario) | Q(alumnos__usuario=usuario),
            futuras,
            evento__estado=Evento.Estado.PROGRAMADO,
        )
        .select_related("evento__turno__cancha__sede")
        .prefetch_related("profesores", "alumnos")
        .distinct()
        .order_by("evento__turno__fecha", "evento__turno__hora_inicio", "pk")[:4]
    )

    actividades = []
    for clase in clases:
        turno = clase.evento.turno
        es_profesor_clase = any(p.profesor_id == usuario.pk for p in clase.profesores.all())
        avisos_ausencia = (
            sum(1 for a in clase.alumnos.all() if a.respuesta == ClaseAlumno.Respuesta.NO_ASISTIRA)
            if es_profesor_clase else 0
        )
        actividades.append({
            "tipo": "clase",
            "id": clase.pk,
            "fecha": turno.fecha,
            "hora_inicio": turno.hora_inicio,
            "hora_fin": turno.hora_fin,
            "referencia": _referencia_fecha(turno.fecha, hoy),
            "sede": turno.cancha.sede.nombre,
            "cancha": turno.cancha.nombre,
            "funcion": "Dictás clase" if es_profesor_clase else "Alumno",
            "funcion_clase": "profesor" if es_profesor_clase else "alumno",
            "avisos_ausencia": avisos_ausencia,
            "url": reverse("clases:clase_detalle", args=[clase.pk]),
        })

    if usuario.puede_reservar:
        reservas = list(
            Reserva.objects.filter(
                Q(organizador=usuario)
                | Q(invitados__usuario=usuario, invitados__respuesta=ReservaInvitado.Respuesta.AFIRMATIVA),
                futuras,
                evento__estado=Evento.Estado.PROGRAMADO,
            )
            .select_related("evento__turno__cancha__sede")
            .distinct()
            .order_by("evento__turno__fecha", "evento__turno__hora_inicio", "pk")[:3]
        )
        for reserva in reservas:
            turno = reserva.evento.turno
            es_organizador = reserva.organizador_id == usuario.pk
            actividades.append({
                "tipo": "reserva",
                "id": reserva.pk,
                "fecha": turno.fecha,
                "hora_inicio": turno.hora_inicio,
                "hora_fin": turno.hora_fin,
                "referencia": _referencia_fecha(turno.fecha, hoy),
                "sede": turno.cancha.sede.nombre,
                "cancha": turno.cancha.nombre,
                "funcion": "Organizador" if es_organizador else "Invitado",
                "funcion_clase": "reserva",
                "avisos_ausencia": 0,
                "url": reverse("reservas:reserva_detalle", args=[reserva.pk]),
            })

    actividades.sort(key=lambda item: (item["fecha"], item["hora_inicio"], item["tipo"], item["id"]))
    return actividades


def _proximos_7_dias(usuario, ahora):
    hoy = ahora.date()
    hasta = hoy + timedelta(days=6)
    futuras = Q(evento__turno__fecha__gt=hoy, evento__turno__fecha__lte=hasta) | Q(
        evento__turno__fecha=hoy, evento__turno__hora_inicio__gt=ahora.time(),
    )

    clases_por_dia = {}
    for fecha in (
        Clase.objects.filter(
            Q(profesores__profesor=usuario) | Q(alumnos__usuario=usuario),
            futuras,
            evento__estado=Evento.Estado.PROGRAMADO,
        )
        .distinct()
        .values_list("evento__turno__fecha", flat=True)
    ):
        clases_por_dia[fecha] = clases_por_dia.get(fecha, 0) + 1

    reservas_por_dia = {}
    if usuario.puede_reservar:
        for fecha in (
            Reserva.objects.filter(
                Q(organizador=usuario)
                | Q(invitados__usuario=usuario, invitados__respuesta=ReservaInvitado.Respuesta.AFIRMATIVA),
                futuras,
                evento__estado=Evento.Estado.PROGRAMADO,
            )
            .distinct()
            .values_list("evento__turno__fecha", flat=True)
        ):
            reservas_por_dia[fecha] = reservas_por_dia.get(fecha, 0) + 1

    dias = []
    for offset in range(7):
        dia = hoy + timedelta(days=offset)
        clases_d = clases_por_dia.get(dia, 0)
        reservas_d = reservas_por_dia.get(dia, 0)
        etiqueta_dia = "Hoy" if offset == 0 else f"{DIAS_CORTOS[dia.isoweekday() - 1]} {dia.day} {MESES_CORTOS[dia.month - 1]}"
        partes = []
        if clases_d:
            partes.append(f"{clases_d} {'clase' if clases_d == 1 else 'clases'}")
        if reservas_d:
            partes.append(f"{reservas_d} {'reserva' if reservas_d == 1 else 'reservas'}")
        tooltip = f"{etiqueta_dia} · {', '.join(partes)}" if partes else f"{etiqueta_dia} · Sin turnos"
        dias.append({
            "fecha": dia,
            "dia_corto": DIAS_CORTOS[dia.isoweekday() - 1],
            "numero": dia.day,
            "es_hoy": offset == 0,
            "clases": clases_d,
            "reservas": reservas_d,
            "total": clases_d + reservas_d,
            "tooltip": tooltip,
        })
    return dias


def _porcentaje(valor, total):
    if total <= 0 or valor <= 0:
        return "0%"
    return f"{min(100.0, (valor / total) * 100):.2f}%"


def _contexto_horas_membresia(usuario, mes, contrato):
    filas = []
    for fila in resumen_horas_del_mes(usuario.pk, mes, contrato):
        limite = max(fila["cupo"] + fila["otorgadas"] - fila["descontadas"], 0)
        usadas = fila["consumidas"] + fila["comprometidas"]
        base = max(limite, usadas, 1)
        filas.append({
            "rol": fila["rol"],
            "disponibles": fila["disponibles"],
            "limite": limite,
            "consumidas": fila["consumidas"],
            "comprometidas": fila["comprometidas"],
            "pct_consumidas": _porcentaje(fila["consumidas"], base),
            "pct_comprometidas": _porcentaje(fila["comprometidas"], base),
            "tooltip": (
                f"{fila['rol']}: {fila['disponibles']} disponibles de {limite} "
                f"({fila['consumidas']} consumidas, {fila['comprometidas']} comprometidas)"
            ),
        })
    return {
        "nombre": contrato.membresia.nombre,
        "url_uso": reverse("membresias:mi_membresia_uso", args=[contrato.pk]),
        "url_detalle": reverse("membresias:mi_membresia_contratado", args=[contrato.pk]),
        "filas": filas,
    }


def _tiene_historial(usuario):
    if usuario.planes_contratados.exists() or usuario.membresias_contratadas.exists():
        return True
    if (
        usuario.clases_como_profesor.exists()
        or usuario.clases_como_participante.exists()
        or usuario.asistencias.exists()
    ):
        return True
    if usuario.puede_reservar and (usuario.reservas.exists() or usuario.invitaciones_reserva.exists()):
        return True
    return False


def contexto_inicio_portal(usuario):
    ahora = timezone.localtime()
    hoy = ahora.date()
    mes = hoy.replace(day=1)
    contexto = {
        "hoy": hoy,
        "mes_actual": mes,
        "pills_estado": [],
        "proxima_actividad": None,
        "siguientes_actividades": [],
        "proximos_7_dias": [],
        "para_revisar": {"filas": [], "todo_al_dia": True},
        "contrataciones_mes": [],
        "horas_membresia": None,
        "asistencia_mes": None,
        "docencia_mes": None,
        "reservas_mes": None,
        "es_cuenta_nueva": False,
        "puede_ver_oferta": usuario.tiene_rol(Rol.PUBLICO),
        "accesos_historial": [],
    }
    if not usuario.esta_habilitado or usuario.debe_cambiar_contrasena:
        return contexto

    es_profesor = usuario.tiene_rol(Rol.PROFESOR)
    es_alumno = usuario.tiene_rol(Rol.ALUMNO)

    actividades = _proximas_actividades(usuario, ahora)
    if actividades:
        contexto["proxima_actividad"] = actividades[0]
        contexto["siguientes_actividades"] = actividades[1:5]
    contexto["proximos_7_dias"] = _proximos_7_dias(usuario, ahora)

    filas_revisar = []
    if usuario.puede_reservar:
        invitaciones = invitaciones_por_responder(usuario, ahora).count()
        filas_revisar.append({
            "texto": "Invitaciones por responder",
            "cantidad": invitaciones,
            "badge_clase": "advertencia" if invitaciones else "sube",
            "url": reverse("reservas:mis_invitaciones", query={"vista": "por_responder"}),
            "accion": "Revisar",
        })
    if es_profesor:
        asistencia_pendiente = clases_sin_asistencia_profesor_queryset(usuario).count()
        filas_revisar.append({
            "texto": "Clases finalizadas sin asistencia cargada",
            "cantidad": asistencia_pendiente,
            "badge_clase": "advertencia" if asistencia_pendiente else "sube",
            "url": reverse(
                "clases:actividad_clases",
                args=[usuario.pk],
                query={"funcion": "profesor", "vista": "asistencia_pendiente", "mes": ""},
            ),
            "accion": "Revisar",
        })

    mes_anterior = (mes - timedelta(days=1)).replace(day=1)
    contrato_membresia_activo = None
    encuestas_pendientes = []
    for tipo, modelo in (("plan", PlanUsuario), ("membresia", MembresiaUsuario)):
        contratos = (
            modelo.objects.filter(usuario=usuario, mes_cubierto__in=(mes, mes_anterior))
            .exclude(estado=modelo.Estado.ANULADO)
            .select_related(tipo)
            .order_by("-mes_cubierto", "pk")
        )
        for contrato in contratos:
            url_detalle = reverse(f"membresias:mi_{tipo}_contratado", args=[contrato.pk])
            if contrato.mes_cubierto == mes and contrato.estado == modelo.Estado.ACTIVO:
                if tipo == "plan":
                    plan = contrato.plan
                    detalle = (
                        f"{plan.frecuencia_semanal} "
                        f"{'encuentro' if plan.frecuencia_semanal == 1 else 'encuentros'}/sem · "
                        f"{plan.cantidad_clases_por_encuentro} h"
                    )
                else:
                    contrato_membresia_activo = contrato
                    detalle = (
                        f"{contrato.horas_organizador_aplicadas} h org. · "
                        f"{contrato.horas_invitado_aplicadas} h inv."
                    )
                contexto["contrataciones_mes"].append({
                    "tipo": "Plan" if tipo == "plan" else "Membresía",
                    "nombre": contrato.producto.nombre,
                    "detalle": detalle,
                    "continuidad": ETIQUETAS_CONTINUIDAD_CORTAS.get(contrato.respuesta_continuidad),
                    "url": url_detalle,
                })
                contexto["pills_estado"].append({
                    "texto": contrato.producto.nombre,
                    "url": url_detalle,
                    "punto_clase": "activo",
                })
            continuidad = contexto_continuidad(contrato, usuario, tipo=tipo)["continuidad"]
            if continuidad["puede_responder"]:
                mes_consultado = MESES_NOMBRES[continuidad["mes_consultado"].month - 1]
                texto_encuesta = f"Continuidad · {contrato.producto.nombre} ({mes_consultado})"
                if not contrato.respuesta_continuidad:
                    url_modal = f"{continuidad['url_responder']}?{urlencode({'siguiente': reverse('inicio')})}"
                    fila_encuesta = {
                        "texto": texto_encuesta,
                        "cantidad": 1,
                        "badge_clase": "advertencia",
                        "url": url_modal,
                        "accion": "Responder",
                        "modal": True,
                    }
                    filas_revisar.append(fila_encuesta)
                    encuestas_pendientes.append(fila_encuesta)
                else:
                    filas_revisar.append({
                        "texto": texto_encuesta,
                        "cantidad": 0,
                        "badge_clase": "sube",
                        "ok_texto": "Respondida",
                    })

    if encuestas_pendientes:
        unica = encuestas_pendientes[0] if len(encuestas_pendientes) == 1 else None
        contexto["pills_estado"].append({
            "texto": "Encuesta abierta" if unica else f"{len(encuestas_pendientes)} encuestas abiertas",
            "url": unica["url"] if unica else "#inicio-revisar-titulo",
            "modal": bool(unica),
            "punto_clase": "primario",
        })

    contexto["para_revisar"] = {
        "filas": filas_revisar,
        "todo_al_dia": all(fila["cantidad"] == 0 for fila in filas_revisar),
    }

    resumen_clases = resumen_clases_mes(usuario, mes)
    if contrato_membresia_activo is not None:
        contexto["horas_membresia"] = _contexto_horas_membresia(usuario, mes, contrato_membresia_activo)

    part = resumen_clases["participante"]
    if es_alumno or part["tiene_actividad"]:
        total_fin = part["finalizadas"]
        contexto["asistencia_mes"] = {
            **part,
            "pct_presentes": _porcentaje(part["presentes"], total_fin),
            "pct_ausentes": _porcentaje(part["ausentes"], total_fin),
            "pct_sin_registrar": _porcentaje(part["sin_registrar"], total_fin),
            "url_clases": reverse(
                "clases:actividad_clases",
                args=[usuario.pk],
                query={"funcion": "participante"} if es_profesor else None,
            ),
        }

    doc = resumen_clases["profesor"]
    if es_profesor:
        contexto["docencia_mes"] = {
            **doc,
            "pct_dictadas": _porcentaje(doc["dictadas"], doc["total"]),
            "url_clases": reverse("clases:actividad_clases", args=[usuario.pk], query={"funcion": "profesor"}),
        }

    if usuario.puede_reservar and contrato_membresia_activo is None:
        organizadas = (
            Reserva.objects.filter(
                organizador=usuario,
                evento__turno__fecha__year=mes.year,
                evento__turno__fecha__month=mes.month,
            )
            .exclude(evento__estado=Evento.Estado.ANULADO)
            .count()
        )
        invitaciones_aceptadas = (
            Reserva.objects.filter(
                invitados__usuario=usuario,
                invitados__respuesta=ReservaInvitado.Respuesta.AFIRMATIVA,
                evento__turno__fecha__year=mes.year,
                evento__turno__fecha__month=mes.month,
            )
            .exclude(organizador=usuario)
            .exclude(evento__estado=Evento.Estado.ANULADO)
            .distinct()
            .count()
        )
        total_reservas_mes = organizadas + invitaciones_aceptadas
        if total_reservas_mes > 0 or (contexto["asistencia_mes"] is None and contexto["docencia_mes"] is None):
            contexto["reservas_mes"] = {
                "organizadas": organizadas,
                "invitaciones": invitaciones_aceptadas,
                "total": total_reservas_mes,
            }

    cantidad_kpis = sum(
        1 for bloque in (
            contexto["horas_membresia"],
            contexto["asistencia_mes"],
            contexto["docencia_mes"],
            contexto["reservas_mes"],
        ) if bloque is not None
    )
    revisar_en_kpis = cantidad_kpis > 0 and not contexto["contrataciones_mes"] and bool(filas_revisar)
    revisar_en_cierre = bool(filas_revisar) and not revisar_en_kpis
    contexto["cantidad_kpis"] = cantidad_kpis
    contexto["revisar_en_kpis"] = revisar_en_kpis
    contexto["revisar_en_cierre"] = revisar_en_cierre
    contexto["mostrar_fila_cierre"] = bool(contexto["contrataciones_mes"]) or revisar_en_cierre

    hay_pendientes = any(fila["cantidad"] > 0 for fila in filas_revisar)
    hay_actividad_mes = (
        bool(contexto["contrataciones_mes"])
        or part["tiene_actividad"]
        or doc["tiene_actividad"]
        or bool(contexto["reservas_mes"] and contexto["reservas_mes"]["total"] > 0)
    )
    contexto["es_cuenta_nueva"] = not actividades and not hay_actividad_mes and not hay_pendientes
    if contexto["es_cuenta_nueva"] and _tiene_historial(usuario):
        if usuario.puede_reservar and (usuario.reservas.exists() or usuario.invitaciones_reserva.exists()):
            contexto["accesos_historial"].append({
                "texto": "Mis reservas", "url": reverse("reservas:mis_reservas"),
            })
        if (
            usuario.clases_como_profesor.exists()
            or usuario.clases_como_participante.exists()
            or usuario.asistencias.exists()
        ):
            contexto["accesos_historial"].append({
                "texto": "Mis clases", "url": reverse("clases:actividad_clases", args=[usuario.pk]),
            })
        if usuario.planes_contratados.exists() or usuario.membresias_contratadas.exists():
            contexto["accesos_historial"].append({
                "texto": "Mis contrataciones", "url": reverse("membresias:mis_contrataciones"),
            })

    return contexto
