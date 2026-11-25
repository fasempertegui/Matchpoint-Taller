from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import formats, timezone

from instalaciones.models import Cancha, Sede
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_eventos
from membresias.fechas import mes_siguiente
from membresias.models import PlanUsuario, RespuestaContinuidad
from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .models import Asistencia, Clase, ClaseAlumno, ClaseProfesor
from .permisos import exigir_acceso_clases, exigir_administracion_clases, puede_dictar_clase
from .validaciones import validar_horario_clase, validar_periodo_actividad_clases

ZONA_SALTA = ZoneInfo("America/Argentina/Salta")

ETIQUETAS_CONTINUIDAD_CORTAS = {
    RespuestaContinuidad.CONTINUAR: "Continuar",
    RespuestaContinuidad.CAMBIAR: "Cambiar",
    RespuestaContinuidad.INDECISO: "Todavía no sé",
    RespuestaContinuidad.NO_CONTINUAR: "No continuar",
}


def clases_sin_asistencia_queryset():
    asistencias_registradas = Asistencia.objects.filter(
        clase_id=OuterRef("clase_id"),
        usuario_id=OuterRef("usuario_id"),
        estado__in=(Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE),
    )
    alumnos_sin_asistencia = ClaseAlumno.objects.filter(
        ~Exists(asistencias_registradas),
        clase_id=OuterRef("pk"),
    )
    asistencias_pendientes = Asistencia.objects.filter(
        clase_id=OuterRef("pk"),
        estado=Asistencia.Estado.SIN_REGISTRAR,
    )
    return Clase.objects.filter(
        Exists(alumnos_sin_asistencia) | Exists(asistencias_pendientes),
        evento__estado=Evento.Estado.FINALIZADO,
    )


def clases_sin_asistencia_profesor_queryset(usuario):
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return Clase.objects.none()
    if not usuario.esta_habilitado or usuario.debe_cambiar_contrasena or not usuario.tiene_rol(Rol.PROFESOR):
        return Clase.objects.none()
    return clases_sin_asistencia_queryset().filter(
        Exists(ClaseProfesor.objects.filter(clase_id=OuterRef("pk"), profesor_id=usuario.pk)),
    )


def consultar_clase(usuario, clase_id):
    usuario = exigir_acceso_clases(usuario)
    clase = Clase.objects.select_related("evento__turno__cancha__sede").get(
        pk=clase_id,
        evento__tipo=Evento.Tipo.CLASE,
    )
    es_administrador = usuario.tiene_rol(Rol.ADMINISTRADOR)
    es_profesor = puede_dictar_clase(usuario, clase)
    profesores = clase.profesores.select_related("profesor")
    participantes = clase.alumnos.select_related("usuario")
    asistencias = clase.asistencias.select_related("usuario")
    puede_consultar_grupo = es_administrador or es_profesor
    if not puede_consultar_grupo:
        participantes = participantes.filter(usuario=usuario)
        asistencias = asistencias.filter(usuario=usuario)
        if not (profesores.filter(profesor=usuario).exists() or participantes.exists() or asistencias.exists()):
            raise PermissionDenied

    turno = clase.evento.turno
    ahora = timezone.localtime()
    inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
    fin = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_fin))
    programada = clase.evento.estado == Evento.Estado.PROGRAMADO
    puede_anular_bloquear = False
    if (
        es_administrador and programada and ahora < inicio
        and turno.cancha.estado == Cancha.Estado.ACTIVA
        and turno.cancha.sede.estado == Sede.Estado.ACTIVA
        and FECHA_INICIO_OPERACIONES <= turno.fecha <= fecha_maxima_eventos()
    ):
        try:
            validar_horario_clase(turno.cancha.sede, turno.fecha, turno.hora_inicio)
        except ValidationError:
            pass
        else:
            puede_anular_bloquear = True
    return {
        "id": clase.pk,
        "evento_id": clase.evento_id,
        "fecha": turno.fecha,
        "hora_inicio": turno.hora_inicio,
        "hora_fin": turno.hora_fin,
        "sede": {"id": turno.cancha.sede_id, "nombre": turno.cancha.sede.nombre},
        "cancha": {"id": turno.cancha_id, "nombre": turno.cancha.nombre},
        "estado": clase.evento.estado,
        "es_generada": clase.es_generada,
        "observaciones": clase.evento.observaciones,
        "creado_en": clase.evento.creado_en,
        "actualizado_en": clase.evento.actualizado_en,
        "registrado_por_id": clase.evento.registrado_por_id if puede_consultar_grupo else None,
        "anulado_por_id": clase.evento.anulado_por_id if puede_consultar_grupo else None,
        "anulado_en": clase.evento.anulado_en,
        "motivo_anulacion": clase.evento.motivo_anulacion,
        "finalizado_por_id": clase.finalizado_por_id if puede_consultar_grupo else None,
        "finalizado_en": clase.evento.finalizado_en,
        "profesores": [
            {
                "usuario_id": asignacion.profesor_id,
                "nombre": str(asignacion.profesor),
                "username": asignacion.profesor.username,
            }
            for asignacion in profesores
        ],
        "participantes": [
            {
                "usuario_id": asignacion.usuario_id,
                "nombre": str(asignacion.usuario),
                "username": asignacion.usuario.username,
                "observaciones": asignacion.observaciones,
                "respuesta_texto": asignacion.get_respuesta_display(),
                "respuesta": asignacion.respuesta,
            }
            for asignacion in participantes
        ],
        "asistencias": [
            {
                "usuario_id": asistencia.usuario_id,
                "nombre": str(asistencia.usuario),
                "username": asistencia.usuario.username,
                "estado": asistencia.estado,
                "observaciones": asistencia.observaciones,
                "registrada_por_id": asistencia.registrada_por_id if puede_consultar_grupo else None,
                "registrada_en": asistencia.registrada_en,
                "actualizado_en": asistencia.actualizado_en,
            }
            for asistencia in asistencias
        ],
        "mi_respuesta": participantes.filter(usuario=usuario).first(),
        "puede_responder": programada and ahora < inicio and participantes.filter(usuario=usuario, respuesta=ClaseAlumno.Respuesta.ASISTIRA).exists(),
        "es_administrador": es_administrador,
        "es_profesor_asignado": es_profesor,
        "puede_editar": es_administrador and programada,
        "puede_cambiar_cancha": es_administrador and programada and ahora < inicio,
        "puede_anular": es_administrador and programada and ahora < inicio,
        "puede_anular_bloquear": puede_anular_bloquear,
        "puede_finalizar": puede_consultar_grupo and programada and ahora >= fin,
        "puede_registrar_asistencia": puede_consultar_grupo and clase.evento.estado == Evento.Estado.FINALIZADO,
    }


def _buscar_usuarios(usuarios, busqueda):
    busqueda = busqueda.strip()
    for termino in busqueda.split():
        usuarios = usuarios.filter(
            Q(first_name__icontains=termino)
            | Q(last_name__icontains=termino)
            | Q(username__icontains=termino)
        )
    return usuarios.order_by("last_name", "first_name", "pk").values(
        "id", "first_name", "last_name", "username",
    )


def consultar_profesores(usuario, busqueda=""):
    exigir_administracion_clases(usuario)
    profesores = Usuario.objects.habilitados().filter(roles__rol__codigo=Rol.PROFESOR)
    return _buscar_usuarios(profesores, busqueda)


def consultar_participantes(usuario, busqueda="", incluir_todos=False):
    exigir_administracion_clases(usuario)
    participantes = Usuario.objects.habilitados()
    if not incluir_todos:
        participantes = participantes.filter(roles__rol__codigo=Rol.ALUMNO)
    return _buscar_usuarios(participantes, busqueda)


def _mes_anterior(mes):
    if mes.month == 1:
        return date(mes.year - 1, 12, 1)
    return date(mes.year, mes.month - 1, 1)


def meses_habilitados_planilla():
    mes_actual = timezone.now().astimezone(ZONA_SALTA).date().replace(day=1)
    return (mes_actual, mes_siguiente(mes_actual))


def participantes_planilla_queryset():
    meses = meses_habilitados_planilla()
    plan_activo = PlanUsuario.objects.filter(
        usuario_id=OuterRef("pk"),
        estado=PlanUsuario.Estado.ACTIVO,
        mes_cubierto__in=meses,
    )
    return Usuario.objects.habilitados().filter(Exists(plan_activo))


def consultar_participantes_planilla(usuario, busqueda=""):
    exigir_administracion_clases(usuario)
    return _buscar_usuarios(participantes_planilla_queryset(), busqueda)


def resumen_comercial_participantes(usuarios_ids, *, mes_objetivo=None):
    ids = list(dict.fromkeys(usuarios_ids))
    if not ids:
        return {}
    if mes_objetivo is None:
        mes_actual, mes_sig = meses_habilitados_planilla()
        mes_ant = _mes_anterior(mes_actual)
        meses_consulta = (mes_ant, mes_actual, mes_sig)
    else:
        mes_ref = mes_objetivo.replace(day=1)
        mes_ant = _mes_anterior(mes_ref)
        meses_consulta = (mes_ant, mes_ref)

    contratos_por_usuario = {}
    contrataciones = PlanUsuario.objects.filter(
        usuario_id__in=ids,
        mes_cubierto__in=meses_consulta,
    ).exclude(
        estado=PlanUsuario.Estado.ANULADO,
    ).select_related("plan")
    for contrato in contrataciones:
        contratos_por_usuario.setdefault(contrato.usuario_id, {})[contrato.mes_cubierto] = contrato

    resumen = {}
    for usuario_id in ids:
        por_mes = contratos_por_usuario.get(usuario_id, {})
        if mes_objetivo is None:
            contrato_actual = por_mes.get(mes_actual)
            contrato_siguiente = por_mes.get(mes_sig)
            if contrato_actual and contrato_actual.estado == PlanUsuario.Estado.ACTIVO:
                plan_activo = contrato_actual
            elif contrato_siguiente and contrato_siguiente.estado == PlanUsuario.Estado.ACTIVO:
                plan_activo = contrato_siguiente
            else:
                plan_activo = None
            contrato_continuidad = contrato_actual if contrato_actual is not None else por_mes.get(mes_ant)
        else:
            contrato_mes = por_mes.get(mes_ref)
            plan_activo = (
                contrato_mes if contrato_mes and contrato_mes.estado == PlanUsuario.Estado.ACTIVO else None
            )
            contrato_continuidad = por_mes.get(mes_ant)

        codigo = contrato_continuidad.respuesta_continuidad if contrato_continuidad else ""
        etiqueta = ETIQUETAS_CONTINUIDAD_CORTAS.get(codigo)
        if codigo == RespuestaContinuidad.CONTINUAR:
            tono = "positivo"
        elif etiqueta:
            tono = "advertencia"
        else:
            tono = None

        plan_texto = None
        if plan_activo is not None:
            mes_texto = formats.date_format(plan_activo.mes_cubierto, "F Y").lower()
            plan_texto = f"{plan_activo.plan.nombre}, {mes_texto}"

        resumen[usuario_id] = {
            "plan_activo": plan_activo,
            "plan_id": plan_activo.pk if plan_activo is not None else None,
            "plan_texto": plan_texto,
            "continuidad_codigo": codigo or None,
            "continuidad_etiqueta": etiqueta,
            "continuidad_texto": f"Respondió: {etiqueta}" if etiqueta else None,
            "continuidad_tono": tono,
        }
    return resumen


def _clases_de_actividad(usuario_id):
    profesores = ClaseProfesor.objects.filter(profesor_id=usuario_id)
    participantes = ClaseAlumno.objects.filter(usuario_id=usuario_id)
    asistencias = Asistencia.objects.filter(usuario_id=usuario_id)
    return Clase.objects.filter(evento__tipo=Evento.Tipo.CLASE).alias(
        tiene_docencia=Exists(profesores.filter(clase_id=OuterRef("pk"))),
        tiene_participacion=Exists(participantes.filter(clase_id=OuterRef("pk"))),
        tiene_asistencia=Exists(asistencias.filter(clase_id=OuterRef("pk"))),
    ).select_related("evento__turno__cancha__sede").prefetch_related(
        Prefetch("profesores", queryset=profesores, to_attr="profesores_del_usuario"),
        Prefetch("alumnos", queryset=participantes, to_attr="participaciones_del_usuario"),
        Prefetch("asistencias", queryset=asistencias, to_attr="asistencias_del_usuario"),
    )


def _fila_actividad_clase(clase):
    profesor = next(iter(clase.profesores_del_usuario), None)
    participante = next(iter(clase.participaciones_del_usuario), None)
    asistencia = next(iter(clase.asistencias_del_usuario), None)
    estado_asistencia = None
    if asistencia is not None:
        estado_asistencia = asistencia.estado
    elif participante is not None:
        estado_asistencia = Asistencia.Estado.SIN_REGISTRAR
    turno = clase.evento.turno
    return {
        "id": clase.pk,
        "fecha": turno.fecha,
        "hora_inicio": turno.hora_inicio,
        "hora_fin": turno.hora_fin,
        "sede": {"id": turno.cancha.sede_id, "nombre": turno.cancha.sede.nombre},
        "cancha": {"id": turno.cancha_id, "nombre": turno.cancha.nombre},
        "estado": clase.evento.estado,
        "estado_texto": clase.evento.get_estado_display(),
        "es_generada": clase.es_generada,
        "asignacion_profesor": profesor is not None,
        "asignacion_participante": participante is not None,
        "respuesta": participante.respuesta if participante else None,
        "respuesta_texto": participante.get_respuesta_display() if participante else None,
        "asistencia": estado_asistencia,
        "asistencia_texto": (
            Asistencia.Estado(estado_asistencia).label
            if clase.evento.estado == Evento.Estado.FINALIZADO and estado_asistencia is not None else None
        ),
        "observaciones_asistencia": asistencia.observaciones if asistencia is not None else None,
        "asistencia_registrada_en": asistencia.registrada_en if asistencia is not None else None,
        "asistencia_actualizada_en": asistencia.actualizado_en if asistencia is not None else None,
    }


def resumen_clases_mes(usuario, mes):
    clases = (
        _clases_de_actividad(usuario.pk)
        .filter(
            Q(tiene_docencia=True) | Q(tiene_participacion=True) | Q(tiene_asistencia=True),
            evento__turno__fecha__year=mes.year,
            evento__turno__fecha__month=mes.month,
        )
        .exclude(evento__estado=Evento.Estado.ANULADO)
    )
    presentes = ausentes = sin_registrar = proximas_participante = 0
    dictadas = proximas_profesor = 0
    for clase in clases:
        fila = _fila_actividad_clase(clase)
        if fila["asignacion_profesor"]:
            if clase.evento.estado == Evento.Estado.FINALIZADO:
                dictadas += 1
            elif clase.evento.estado == Evento.Estado.PROGRAMADO:
                proximas_profesor += 1
        if fila["asignacion_participante"] or fila["asistencia"] is not None:
            if clase.evento.estado == Evento.Estado.FINALIZADO:
                if fila["asistencia"] == Asistencia.Estado.PRESENTE:
                    presentes += 1
                elif fila["asistencia"] == Asistencia.Estado.AUSENTE:
                    ausentes += 1
                elif fila["asistencia"] == Asistencia.Estado.SIN_REGISTRAR:
                    sin_registrar += 1
            elif clase.evento.estado == Evento.Estado.PROGRAMADO and fila["asignacion_participante"]:
                proximas_participante += 1
    finalizadas_participante = presentes + ausentes + sin_registrar
    total_profesor = dictadas + proximas_profesor
    return {
        "participante": {
            "presentes": presentes,
            "ausentes": ausentes,
            "sin_registrar": sin_registrar,
            "finalizadas": finalizadas_participante,
            "proximas": proximas_participante,
            "tiene_actividad": finalizadas_participante > 0 or proximas_participante > 0,
        },
        "profesor": {
            "dictadas": dictadas,
            "proximas": proximas_profesor,
            "total": total_profesor,
            "tiene_actividad": total_profesor > 0,
        },
    }


def consultar_mis_clases(usuario, *, mes, estado, funcion, numero_pagina, asistencia_pendiente=False):
    usuario = exigir_acceso_clases(usuario)
    clases = _clases_de_actividad(usuario.pk)
    if mes:
        inicio_mes = date.fromisoformat(f"{mes}-01")
        fin_mes = inicio_mes.replace(day=monthrange(inicio_mes.year, inicio_mes.month)[1])
        desde = max(FECHA_INICIO_OPERACIONES, inicio_mes)
        hasta = min(fecha_maxima_eventos(), fin_mes)
        clases = clases.filter(evento__turno__fecha__range=(desde, hasta))
    elif not asistencia_pendiente:
        clases = clases.filter(evento__turno__fecha__range=(FECHA_INICIO_OPERACIONES, fecha_maxima_eventos()))

    if asistencia_pendiente:
        clases = clases.filter(pk__in=clases_sin_asistencia_profesor_queryset(usuario).values("pk"))
    else:
        if funcion == "profesor":
            clases = clases.filter(tiene_docencia=True)
        elif funcion == "participante":
            clases = clases.filter(Q(tiene_participacion=True) | Q(tiene_asistencia=True))
        else:
            clases = clases.filter(Q(tiene_docencia=True) | Q(tiene_participacion=True) | Q(tiene_asistencia=True))
        if estado:
            clases = clases.filter(evento__estado=estado)

    clases = clases.order_by("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
    pagina = Paginator(clases, 10).get_page(numero_pagina)
    pagina.object_list = [_fila_actividad_clase(clase) for clase in pagina]
    return pagina


def consultar_actividad_clases(usuario, fecha_desde, fecha_hasta, usuario_id=None):
    usuario = exigir_acceso_clases(usuario)
    if usuario_id is None:
        usuario_id = usuario.pk
    if type(usuario_id) is not int or usuario_id <= 0:
        raise ValidationError("Elegí un usuario válido para consultar su actividad.")
    if usuario_id != usuario.pk and not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    validar_periodo_actividad_clases(fecha_desde, fecha_hasta)
    titular = Usuario.objects.get(pk=usuario_id)
    clases = _clases_de_actividad(titular.pk).filter(
        Q(tiene_docencia=True) | Q(tiene_participacion=True) | Q(tiene_asistencia=True),
        evento__turno__fecha__range=(fecha_desde, fecha_hasta),
    ).annotate(
        asistencia_cargada=Exists(Asistencia.objects.filter(
            clase_id=OuterRef("pk"), estado__in=(Asistencia.Estado.PRESENTE, Asistencia.Estado.AUSENTE),
        )),
    ).order_by("evento__turno__fecha", "evento__turno__hora_inicio", "pk")

    ahora = timezone.localtime()
    actividad = []
    proximas = []
    anuladas = []
    totales = {
        "clases_asignadas": 0,
        "clases_como_profesor": 0,
        "presentes": 0,
        "ausentes": 0,
        "sin_registrar": 0,
        "anuladas": 0,
    }
    for clase in clases:
        fila = _fila_actividad_clase(clase)
        fila["asistencia_cargada"] = clase.asistencia_cargada
        profesor_activo = fila["asignacion_profesor"]
        participante_activo = fila["asignacion_participante"]
        estado_asistencia = fila["asistencia"]
        turno = clase.evento.turno
        if clase.evento.estado == Evento.Estado.ANULADO:
            anuladas.append(fila)
            totales["anuladas"] += 1
            continue
        actividad.append(fila)
        if participante_activo:
            totales["clases_asignadas"] += 1
        if profesor_activo:
            totales["clases_como_profesor"] += 1
        # Una clase aún Programada no acredita asistencia ni ausencia efectiva.
        if clase.evento.estado == Evento.Estado.FINALIZADO:
            if estado_asistencia == Asistencia.Estado.PRESENTE:
                totales["presentes"] += 1
            elif estado_asistencia == Asistencia.Estado.AUSENTE:
                totales["ausentes"] += 1
            elif estado_asistencia == Asistencia.Estado.SIN_REGISTRAR:
                totales["sin_registrar"] += 1
        inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
        if (
            clase.evento.estado == Evento.Estado.PROGRAMADO and inicio > ahora
            and (profesor_activo or participante_activo)
        ):
            proximas.append(fila)
    return {
        "usuario": {"id": titular.pk, "nombre": str(titular)},
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "totales": totales,
        "clases": actividad,
        "proximas": proximas,
        "anuladas": anuladas,
    }
