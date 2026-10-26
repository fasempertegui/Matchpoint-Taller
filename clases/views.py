from calendar import monthrange
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from common.fechas import FECHA_INICIO_OPERACIONES
from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .anulaciones import confirmar_anulacion_clase, preparar_anulacion_clase, validar_accion_anulacion
from .consultas import consultar_actividad_clases, consultar_clase, consultar_profesores, consultar_participantes
from .forms import ActividadClasesForm, AsistenciaEditorForm, AsistenciaFormSet, ClaseAnulacionForm, ClaseCanchaForm, ClaseForm, ClaseTurnoForm
from .models import Asistencia, Clase, TurnoPlanilla
from .permisos import exigir_acceso_clases, exigir_administracion_clases
from .servicios import (
    cambiar_cancha_clase, consultar_edicion_clase, editar_clase,
    preparar_cambio_cancha, preparar_edicion_clase,
    consultar_clase_para_asistencia, finalizar_clase, preparar_carga_asistencia,
    preparar_registro_clase, registrar_asistencia, registrar_clase, validar_ubicacion_clase,
)


@login_required
@never_cache
@require_GET
def clase_detalle(request, pk):
    try:
        clase = consultar_clase(request.user, pk)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None

    clase["estado_texto"] = Evento.Estado(clase["estado"]).label
    clase["modalidad_texto"] = (
        TurnoPlanilla.Modalidad(clase["modalidad"]).label if clase["modalidad"] else "Sin especificar"
    )
    puede_consultar_grupo = clase["es_administrador"] or clase["es_profesor_asignado"]
    responsables = {}
    if puede_consultar_grupo:
        responsables = Usuario.objects.in_bulk({
            clase[campo] for campo in ("registrado_por_id", "anulado_por_id", "finalizado_por_id")
            if clase[campo] is not None
        })
    asistencias = {fila["usuario_id"]: fila for fila in clase["asistencias"]}
    for participante in clase["participantes"]:
        if participante["estado"] == "activo":
            asistencia = asistencias.get(participante["usuario_id"], {"estado": Asistencia.Estado.SIN_REGISTRAR})
            participante["asistencia_texto"] = Asistencia.Estado(asistencia["estado"]).label
            participante["badge_asistencia"] = "activo" if asistencia["estado"] == Asistencia.Estado.PRESENTE else "inactivo"
            participante["observaciones_asistencia"] = asistencia.get("observaciones")

    for seccion in ("profesores", "participantes"):
        clase[seccion].sort(key=lambda persona: (
            persona["estado"] != "activo", persona["nombre"].casefold(), persona["usuario_id"],
        ))
        clase[f"{seccion}_vigentes"] = sum(persona["estado"] == "activo" for persona in clase[seccion])
        clase[f"{seccion}_retirados"] = len(clase[seccion]) - clase[f"{seccion}_vigentes"]

    url_agenda = reverse("agenda:agenda") + "?" + urlencode({
        "sede": clase["sede"]["id"],
        "cancha": clase["cancha"]["id"],
        "fecha": clase["fecha"].isoformat(),
        "hora": clase["hora_inicio"].hour,
    })
    return render(request, "clases/clase_detalle.html", {
        "clase": clase,
        "puede_consultar_grupo": puede_consultar_grupo,
        "solo_propios": not puede_consultar_grupo,
        "mostrar_asistencia": clase["estado"] == Evento.Estado.FINALIZADO,
        "hay_asistencia": bool(clase["asistencias"]),
        "titulo_profesores": "Profesores",
        "titulo_participantes": "Participantes" if puede_consultar_grupo else "Mi participación",
        "registrado_por": responsables.get(clase["registrado_por_id"]),
        "anulado_por": responsables.get(clase["anulado_por_id"]),
        "finalizado_por": responsables.get(clase["finalizado_por_id"]),
        "url_agenda": url_agenda,
        "breadcrumbs": [
            ("Inicio", reverse("inicio")),
            ("Agenda", url_agenda),
            (f"Clase {clase['id']}", None),
        ],
    })


@login_required
@never_cache
@require_GET
def buscar_personas(request):
    exigir_administracion_clases(request.user)
    busqueda = request.GET.get("q", "").strip()[:100]
    tipo = request.GET.get("tipo")
    if tipo not in ("profesores", "participantes"):
        return JsonResponse({"error": "Elegí profesores o participantes."}, status=400)
    if len(busqueda) < 2:
        return JsonResponse({"resultados": [], "hay_mas": False})
    if tipo == "profesores":
        personas = consultar_profesores(request.user, busqueda)
    else:
        personas = consultar_participantes(request.user, busqueda, request.GET.get("todos") == "1")
    excluidos = [
        int(valor) for valor in request.GET.getlist("excluir")[:200]
        if valor.isdecimal() and len(valor) < 19
    ]
    filas = list(personas.exclude(pk__in=excluidos)[:11])
    return JsonResponse({
        "resultados": [
            {
                "id": fila["id"],
                "nombre": f"{fila['first_name']} {fila['last_name']}".strip() or fila["username"],
                "usuario": fila["username"],
            }
            for fila in filas[:10]
        ],
        "hay_mas": len(filas) > 10,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_crear(request):
    usuario = exigir_administracion_clases(request.user)
    ubicacion = ClaseTurnoForm(request.GET)
    if not ubicacion.is_valid():
        messages.error(request, "Elegí una cancha, fecha y hora válidas desde la agenda.")
        return redirect("agenda:agenda")
    cancha = ubicacion.cleaned_data["cancha"]
    fecha = ubicacion.cleaned_data["fecha"]
    hora = time(ubicacion.cleaned_data["hora"])
    url_agenda = reverse("agenda:agenda") + "?" + urlencode({
        "sede": cancha.sede_id, "cancha": cancha.pk, "fecha": fecha.isoformat(), "hora": hora.hour,
    })
    formulario = ClaseForm(request.POST if request.method == "POST" else None)
    revision = None
    impedimento = None
    try:
        validar_ubicacion_clase(cancha, fecha, hora)
    except ValidationError as error:
        impedimento = " ".join(error.messages)
    if request.method == "POST" and formulario.is_valid():
        paso = request.POST.get("paso")
        try:
            if impedimento:
                raise ValidationError(impedimento)
            if paso == "confirmar":
                clase = registrar_clase(
                    usuario, cancha, fecha, hora, **formulario.parametros(),
                    confirmacion=request.POST.get("confirmacion", ""),
                )
                messages.success(request, "La clase fue creada.")
                return redirect("clases:clase_detalle", pk=clase.pk)
            if paso == "revisar":
                revision = preparar_registro_clase(usuario, cancha, fecha, hora, **formulario.parametros())
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)
    return render(request, "clases/clase_formulario.html", {
        "formulario": formulario, "revision": revision,
        "profesores": formulario.seleccionados("profesores"),
        "participantes": formulario.seleccionados("participantes"),
        "modalidad_texto": dict(formulario.fields["modalidad"].choices).get(formulario["modalidad"].value(), "Sin especificar"),
        "cancha": cancha, "fecha": fecha, "hora": hora,
        "hora_fin": (datetime.combine(fecha, hora) + timedelta(hours=1)).time(),
        "url_agenda": url_agenda, "url_cancelar": url_agenda, "impedimento": impedimento,
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Agenda", url_agenda), ("Crear clase", None)],
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_editar(request, pk):
    usuario = exigir_administracion_clases(request.user)
    url_detalle = reverse("clases:clase_detalle", args=[pk])
    try:
        datos = consultar_edicion_clase(usuario, pk)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect(url_detalle)
    clase = datos["clase"]
    turno = clase.evento.turno
    version = request.POST.get("version", "") if request.method == "POST" else datos["version"]
    formulario = ClaseForm(
        request.POST if request.method == "POST" else None,
        initial={
            "profesores": datos["profesores_ids"], "participantes": datos["participantes_ids"],
            "modalidad": clase.modalidad or "", "observaciones": clase.evento.observaciones,
        },
        profesores_actuales=datos["profesores_ids"], participantes_actuales=datos["participantes_ids"],
    )
    revision = None
    if request.method == "POST" and formulario.is_valid():
        paso = request.POST.get("paso")
        try:
            if paso == "confirmar":
                editar_clase(usuario, pk, **formulario.parametros(), confirmacion=request.POST.get("confirmacion", ""))
                messages.success(request, "Los cambios de la clase fueron guardados.")
                return redirect(url_detalle)
            if paso == "revisar":
                revision = preparar_edicion_clase(usuario, pk, **formulario.parametros(), version=version)
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)
    return render(request, "clases/clase_formulario.html", {
        "editando": True, "clase_id": pk, "version": version,
        "formulario": formulario, "revision": revision,
        "profesores": formulario.seleccionados("profesores"),
        "participantes": formulario.seleccionados("participantes"),
        "modalidad_texto": dict(formulario.fields["modalidad"].choices).get(formulario["modalidad"].value(), "Sin especificar"),
        "cancha": turno.cancha, "fecha": turno.fecha,
        "hora": turno.hora_inicio, "hora_fin": turno.hora_fin,
        "url_cancelar": url_detalle,
        "breadcrumbs": [("Inicio", reverse("inicio")), (f"Clase {pk}", url_detalle), ("Editar", None)],
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_cambiar_cancha(request, pk):
    usuario = exigir_administracion_clases(request.user)
    url_detalle = reverse("clases:clase_detalle", args=[pk])
    try:
        datos = consultar_edicion_clase(usuario, pk)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect(url_detalle)
    clase = datos["clase"]
    turno = clase.evento.turno
    inicio = timezone.make_aware(datetime.combine(turno.fecha, turno.hora_inicio))
    if timezone.localtime() >= inicio:
        messages.error(request, "Sólo se puede cambiar de cancha antes del inicio de la clase.")
        return redirect(url_detalle)
    version = request.POST.get("version", "") if request.method == "POST" else datos["version"]
    formulario = ClaseCanchaForm(request.POST if request.method == "POST" else None, clase=clase)
    confirmacion = None
    destino = None
    if request.method == "POST" and formulario.is_valid():
        destino = formulario.cleaned_data["cancha"]
        paso = request.POST.get("paso")
        try:
            if paso == "confirmar":
                cambiar_cancha_clase(usuario, pk, destino, confirmacion=request.POST.get("confirmacion", ""))
                messages.success(request, "La clase cambió de cancha. La cancha original quedó disponible para ese turno.")
                return redirect(url_detalle)
            if paso == "revisar":
                confirmacion = preparar_cambio_cancha(usuario, pk, destino, version=version)
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)
        except Clase.DoesNotExist:
            raise Http404("La clase no existe.") from None
    return render(request, "clases/clase_cambiar_cancha.html", {
        "clase": clase, "turno": turno, "formulario": formulario,
        "version": version, "confirmacion": confirmacion, "destino": destino,
        "hay_destinos": formulario.fields["cancha"].queryset.exists(),
        "url_detalle": url_detalle,
        "breadcrumbs": [("Inicio", reverse("inicio")), (f"Clase {pk}", url_detalle), ("Cambiar de cancha", None)],
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_anular(request, pk, bloquear=False):
    usuario = exigir_administracion_clases(request.user)
    url_detalle = reverse("clases:clase_detalle", args=[pk])
    try:
        datos = consultar_edicion_clase(usuario, pk)
        validar_accion_anulacion(datos["clase"], bloquear)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect(url_detalle)
    clase = datos["clase"]
    version = request.POST.get("version", "") if request.method == "POST" else datos["version"]
    formulario = ClaseAnulacionForm(request.POST if request.method == "POST" else None, bloquear=bloquear)
    confirmacion = None
    if request.method == "POST" and formulario.is_valid():
        parametros = {"bloquear": bloquear, **formulario.cleaned_data}
        paso = request.POST.get("paso")
        try:
            if paso == "confirmar":
                confirmar_anulacion_clase(usuario, pk, **parametros, confirmacion=request.POST.get("confirmacion", ""))
                messages.success(request, "La clase fue anulada y su turno quedó bloqueado." if bloquear else "La clase fue anulada y su turno quedó libre.")
                return redirect(url_detalle)
            if paso == "revisar":
                confirmacion = preparar_anulacion_clase(usuario, pk, **parametros, version=version)
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)
        except Clase.DoesNotExist:
            raise Http404("La clase no existe.") from None
    return render(request, "clases/clase_anular.html", {
        "clase": clase, "turno": clase.evento.turno, "bloquear": bloquear,
        "formulario": formulario, "confirmacion": confirmacion, "version": version,
        "motivo_bloqueo": dict(formulario.fields["motivo_bloqueo"].choices).get(formulario["motivo_bloqueo"].value(), "") if bloquear else "",
        "url_detalle": url_detalle,
        "breadcrumbs": [("Inicio", reverse("inicio")), (f"Clase {pk}", url_detalle), ("Anular y bloquear" if bloquear else "Anular y liberar", None)],
    })


@login_required
@never_cache
@require_POST
def clase_finalizar(request, pk):
    try:
        finalizar_clase(pk, usuario=request.user)
    except (Clase.DoesNotExist, Evento.DoesNotExist):
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        try:
            clase = consultar_clase(request.user, pk)
        except Clase.DoesNotExist:
            raise Http404("La clase no existe.") from None
        if clase["estado"] == Evento.Estado.FINALIZADO:
            messages.info(request, "La clase ya está finalizada.")
        else:
            for mensaje in error.messages:
                messages.error(request, mensaje)
    else:
        messages.success(request, "La clase fue finalizada. La asistencia se conserva sin cambios.")
    return redirect("clases:clase_detalle", pk=pk)


@login_required
@never_cache
@require_GET
def buscar_personas_asistencia(request, pk):
    try:
        consultar_clase_para_asistencia(request.user, pk)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
    busqueda = request.GET.get("q", "").strip()[:100]
    if len(busqueda) < 2:
        return JsonResponse({"resultados": [], "hay_mas": False})
    personas = Usuario.objects.all()
    for termino in busqueda.split():
        personas = personas.filter(Q(first_name__icontains=termino) | Q(last_name__icontains=termino) | Q(username__icontains=termino))
    excluidos = [int(valor) for valor in request.GET.getlist("excluir")[:200] if valor.isdecimal() and len(valor) < 19]
    personas = list(personas.exclude(pk__in=excluidos).order_by("last_name", "first_name", "pk")[:11])
    return JsonResponse({
        "resultados": [{"id": persona.pk, "nombre": str(persona), "usuario": persona.username, "activa": persona.is_active} for persona in personas[:10]],
        "hay_mas": len(personas) > 10,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_asistencia(request, pk):
    url_detalle = reverse("clases:clase_detalle", args=[pk])
    try:
        datos = preparar_carga_asistencia(request.user, pk)
    except Clase.DoesNotExist:
        raise Http404("La clase no existe.") from None
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect(url_detalle)
    clase = datos["clase"]
    version = request.POST.get("version", "") if request.method == "POST" else datos["version"]
    formularios = AsistenciaFormSet(
        request.POST if request.method == "POST" else None, initial=datos["registros"], prefix="asistencias",
    )
    error_guardado = None
    if request.method == "POST" and formularios.is_valid():
        registros = [
            {"usuario_id": fila.cleaned_data["usuario"], "estado": fila.cleaned_data["estado"], "observaciones": fila.cleaned_data["observaciones"]}
            for fila in formularios if fila.cleaned_data
        ]
        try:
            if request.POST.get("paso") != "guardar":
                raise ValidationError("La acción solicitada no es válida.")
            registrar_asistencia(request.user, pk, registros, finalizar=True, version=version)
            messages.success(request, "La asistencia fue guardada.")
            return redirect(url_detalle)
        except ValidationError as error:
            error_guardado = " ".join(error.messages)
        except (Clase.DoesNotExist, Evento.DoesNotExist):
            raise Http404("La clase no existe.") from None
    filas = []
    ids = [int(fila["usuario"].value()) for fila in formularios if str(fila["usuario"].value()).isdecimal() and len(str(fila["usuario"].value())) < 19]
    personas = Usuario.objects.in_bulk(ids)
    base = {fila["usuario"] for fila in datos["registros"]}
    for fila in formularios:
        valor = str(fila["usuario"].value())
        persona = personas.get(int(valor)) if valor.isdecimal() and len(valor) < 19 else None
        estado = fila["estado"].value()
        filas.append({
            "formulario": fila, "persona": persona,
            "estado_texto": dict(Asistencia.Estado.choices).get(estado, "Sin registrar"),
            "badge": "activo" if estado == Asistencia.Estado.PRESENTE else "inactivo",
            "quitable": persona is not None and persona.pk not in base,
        })
    return render(request, "clases/clase_asistencia.html", {
        "clase": clase, "turno": clase.evento.turno, "formularios": formularios,
        "filas": filas, "editor": AsistenciaEditorForm(prefix="editor"),
        "fila_vacia": {"formulario": formularios.empty_form, "quitable": True, "badge": "inactivo", "estado_texto": "Sin registrar"},
        "version": version, "error_guardado": error_guardado,
        "finalizar": clase.evento.estado == Evento.Estado.PROGRAMADO,
        "url_detalle": url_detalle,
        "breadcrumbs": [("Inicio", reverse("inicio")), (f"Clase {pk}", url_detalle), ("Asistencia", None)],
    })


@login_required
@never_cache
@require_GET
def actividad_clases(request, usuario_id):
    usuario = exigir_acceso_clases(request.user)
    if usuario.pk != usuario_id and not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    titular = get_object_or_404(Usuario, pk=usuario_id)
    roles = set(titular.roles.values_list("rol__codigo", flat=True))
    es_profesor = Rol.PROFESOR in roles
    es_alumno = Rol.ALUMNO in roles
    hoy = timezone.localdate()
    parametros = request.GET.copy()
    parametros.setdefault("fecha_desde", max(hoy.replace(day=1), FECHA_INICIO_OPERACIONES).isoformat())
    parametros.setdefault("fecha_hasta", hoy.replace(day=monthrange(hoy.year, hoy.month)[1]).isoformat())
    parametros.setdefault("vista", "proximas")
    formulario = ActividadClasesForm(parametros)
    actividad = None
    resumen = None
    pagina = None
    vistas = []
    url_anterior = None
    url_siguiente = None
    if formulario.is_valid():
        filtros = formulario.cleaned_data
        actividad = consultar_actividad_clases(
            usuario, filtros["fecha_desde"], filtros["fecha_hasta"], usuario_id=usuario_id,
        )
        if es_profesor:
            campo_asignacion = "asignacion_profesor"
        elif es_alumno:
            campo_asignacion = "asignacion_participante"
        else:
            campo_asignacion = None
        if campo_asignacion:
            actividad["proximas"] = [
                fila for fila in actividad["proximas"] if fila[campo_asignacion] == "activo"
            ]
            for grupo in ("clases", "anuladas"):
                actividad[grupo] = [
                    fila for fila in actividad[grupo]
                    if fila[campo_asignacion] is not None or (es_alumno and fila["asistencia"] is not None)
                ]
        finalizadas = [fila for fila in actividad["clases"] if fila["estado"] == Evento.Estado.FINALIZADO]
        if es_profesor:
            dictadas = [fila for fila in finalizadas if fila["asignacion_profesor"] == "activo"]
            resumen = {
                "dictadas": len(dictadas), "proximas": len(actividad["proximas"]),
                "sin_cargar": sum(not fila["asistencia_cargada"] for fila in dictadas),
            }
        else:
            asistencias = [fila["asistencia"] for fila in finalizadas if fila["asistencia"] is not None]
            resumen = {
                "clases": sum(fila["asignacion_participante"] == "activo" for fila in actividad["clases"]),
                "finalizadas": len(asistencias), "presentes": asistencias.count(Asistencia.Estado.PRESENTE),
                "ausentes": asistencias.count(Asistencia.Estado.AUSENTE),
                "sin_registrar": asistencias.count(Asistencia.Estado.SIN_REGISTRAR),
            }
        ids_proximas = {fila["id"] for fila in actividad["proximas"]}
        grupos = {
            "proximas": actividad["proximas"],
            "historial": [fila for fila in actividad["clases"] if fila["id"] not in ids_proximas],
            "anuladas": actividad["anuladas"],
        }
        grupos["historial"].sort(key=lambda fila: (fila["fecha"], fila["hora_inicio"], fila["id"]), reverse=True)
        grupos["anuladas"].sort(key=lambda fila: (fila["fecha"], fila["hora_inicio"], fila["id"]), reverse=True)
        enlaces = {
            "fecha_desde": filtros["fecha_desde"].isoformat(),
            "fecha_hasta": filtros["fecha_hasta"].isoformat(),
        }
        for codigo, nombre in formulario.fields["vista"].choices:
            vistas.append({
                "nombre": nombre, "actual": codigo == filtros["vista"],
                "url": request.path + "?" + urlencode({**enlaces, "vista": codigo}),
            })
        pagina = Paginator(grupos[filtros["vista"]], 10).get_page(request.GET.get("pagina"))
        for fila in pagina:
            fila["estado_texto"] = Evento.Estado(fila["estado"]).label
            fila["modalidad_texto"] = TurnoPlanilla.Modalidad(fila["modalidad"]).label if fila["modalidad"] else "Sin especificar"
            fila["asistencia_texto"] = None
            if es_alumno and fila["estado"] == Evento.Estado.FINALIZADO and fila["asistencia"] is not None:
                fila["asistencia_texto"] = Asistencia.Estado(fila["asistencia"]).label
                fila["badge_asistencia"] = "activo" if fila["asistencia"] == Asistencia.Estado.PRESENTE else "inactivo"
        enlaces["vista"] = filtros["vista"]
        if pagina.has_previous():
            url_anterior = request.path + "?" + urlencode({**enlaces, "pagina": pagina.previous_page_number()})
        if pagina.has_next():
            url_siguiente = request.path + "?" + urlencode({**enlaces, "pagina": pagina.next_page_number()})
    url_perfil = reverse("usuarios:usuario_detalle", args=[usuario_id])
    return render(request, "clases/actividad_clases.html", {
        "titular": titular, "actividad": actividad, "formulario": formulario,
        "es_profesor": es_profesor, "es_alumno": es_alumno, "resumen": resumen,
        "vistas": vistas, "pagina": pagina, "url_anterior": url_anterior, "url_siguiente": url_siguiente,
        "url_perfil": url_perfil,
        "breadcrumbs": [("Inicio", reverse("inicio")), (str(titular), url_perfil), ("Actividad de clases", None)],
    })
