from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from reservas.models import Evento
from usuarios.models import Usuario

from .consultas import consultar_clase, consultar_profesores, consultar_participantes
from .forms import ClaseCanchaForm, ClaseForm, ClaseTurnoForm
from .models import Asistencia, Clase, TurnoPlanilla
from .permisos import exigir_administracion_clases
from .servicios import (
    cambiar_cancha_clase, consultar_edicion_clase, editar_clase,
    preparar_cambio_cancha, preparar_edicion_clase,
    preparar_registro_clase, registrar_clase, validar_ubicacion_clase,
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
        asistencia = asistencias.pop(participante["usuario_id"], None)
        participante["asistencia"] = (
            Asistencia.Estado(asistencia["estado"]).label if asistencia else "Sin registrar"
        )
    for asistencia in asistencias.values():
        asistencia["estado_texto"] = Asistencia.Estado(asistencia["estado"]).label

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
        "titulo_profesores": "Profesores" if puede_consultar_grupo else "Mi asignación como profesor",
        "titulo_participantes": "Participantes" if puede_consultar_grupo else "Mi participación",
        "registrado_por": responsables.get(clase["registrado_por_id"]),
        "anulado_por": responsables.get(clase["anulado_por_id"]),
        "finalizado_por": responsables.get(clase["finalizado_por_id"]),
        "asistencias_adicionales": list(asistencias.values()),
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
