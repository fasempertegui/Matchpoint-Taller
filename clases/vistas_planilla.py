from datetime import time
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from instalaciones.models import Cancha, Sede

from .forms import ObservacionesPlanillaForm, PlanillaFiltroForm
from .models import TurnoPlanilla
from .permisos import exigir_administracion_clases
from .planilla import (
    consultar_planilla, editar_turno_planilla, quitar_turno_planilla, quitar_turnos_planilla,
    registrar_turnos_planilla, validar_version_turno_planilla, version_turno_planilla,
)
from .validaciones import validar_horario_planilla


def _url_planilla(cancha):
    return reverse("clases:planilla") + "?" + urlencode({"sede": cancha.sede_id, "cancha": cancha.pk})


@login_required
@never_cache
@require_GET
def planilla(request):
    usuario = exigir_administracion_clases(request.user)
    parametros = request.GET.copy()
    sede = Sede.objects.order_by("estado", "nombre", "pk").first()
    if sede:
        parametros.setdefault("sede", str(sede.pk))
    formulario = PlanillaFiltroForm(parametros)
    primera_cancha = formulario.fields["cancha"].queryset.first()
    if primera_cancha:
        parametros.setdefault("cancha", str(primera_cancha.pk))
        formulario = PlanillaFiltroForm(parametros)
    filas = []
    datos = None
    cancha = None
    if sede and formulario.is_valid():
        cancha = formulario.cleaned_data["cancha"]
        datos = consultar_planilla(usuario, cancha.sede_id, cancha.pk)
        turnos = {(turno["dia_semana"], turno["hora_inicio"].hour): turno for turno in datos["turnos"]}
        horarios = {horario.dia_semana: horario for horario in cancha.sede.horarios.all()}
        horas = set(hora for _, hora in turnos)
        habilitadas = set()
        for dia, horario in horarios.items():
            franjas = [(horario.hora_inicio_1, horario.hora_fin_1)]
            if horario.hora_inicio_2 is not None:
                franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
            for inicio, fin in franjas:
                for hora in range(inicio.hour, fin.hour):
                    habilitadas.add((dia, hora))
                    horas.add(hora)
        if horas:
            for hora in range(min(horas), max(horas) + 1):
                if hora not in horas:
                    if filas and filas[-1].get("pausa"):
                        filas[-1]["fin"] = time(hora + 1)
                    else:
                        filas.append({"pausa": True, "inicio": time(hora), "fin": time(hora + 1)})
                    continue
                celdas = []
                for dia, nombre in TurnoPlanilla.DiaSemana.choices:
                    turno = turnos.get((dia, hora))
                    habilitada = (dia, hora) in habilitadas
                    url = None
                    if turno:
                        url = reverse("clases:planilla_detalle", args=[turno["id"]])
                    seleccionable = habilitada and cancha.estado == Cancha.Estado.ACTIVA and cancha.sede.estado == Sede.Estado.ACTIVA
                    celdas.append({
                        "turno": turno, "habilitada": habilitada, "url": url, "dia": nombre,
                        "numero_dia": dia, "seleccionable": seleccionable,
                    })
                filas.append({"hora": time(hora), "celdas": celdas, "seleccionable": any(c["seleccionable"] for c in celdas)})
    return render(request, "clases/planilla.html", {
        "formulario": formulario,
        "hay_sedes": sede is not None, "hay_canchas": primera_cancha is not None,
        "datos": datos, "cancha": cancha, "filas": filas,
        "dias": TurnoPlanilla.DiaSemana.labels,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def planilla_detalle(request, pk):
    usuario = exigir_administracion_clases(request.user)
    turno = get_object_or_404(TurnoPlanilla.objects.select_related("cancha__sede"), pk=pk)
    if request.method == "POST":
        try:
            if request.POST.get("accion") != "quitar":
                raise ValidationError("La acción solicitada no es válida.")
            quitar_turno_planilla(usuario, pk, version=request.POST.get("version", ""))
            messages.success(request, "El horario fue quitado de la planilla. Las clases existentes se conservan.")
            return redirect(_url_planilla(turno.cancha))
        except TurnoPlanilla.DoesNotExist:
            raise Http404("El horario ya no existe en la planilla.") from None
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)
            return redirect("clases:planilla_detalle", pk=pk)
    return render(request, "clases/planilla_detalle.html", {
        "turno": turno, "hora_fin": time(turno.hora_inicio.hour + 1),
        "profesores": [v.profesor for v in turno.profesores.select_related("profesor").order_by("profesor_id")],
        "participantes": [v.usuario for v in turno.alumnos.select_related("usuario").order_by("usuario_id")],
        "version": version_turno_planilla(turno), "url_planilla": _url_planilla(turno.cancha),
        "puede_editar": turno.cancha.estado == Cancha.Estado.ACTIVA and turno.cancha.sede.estado == Sede.Estado.ACTIVA,
    })


@login_required
@never_cache
@require_POST
def planilla_crear(request):
    usuario = exigir_administracion_clases(request.user)
    cancha_id = request.POST.get("cancha", "")
    if not cancha_id.isdecimal() or len(cancha_id) > 18:
        raise Http404("Elegí una cancha válida de la planilla.")
    cancha = get_object_or_404(Cancha.objects.select_related("sede"), pk=int(cancha_id))
    try:
        valores = request.POST.getlist("turno")
        if not valores or len(valores) > 161:
            raise ValidationError("Seleccioná los horarios que querés crear.")
        coordenadas = []
        for valor in valores:
            partes = valor.split("-")
            if len(partes) != 2 or any(not parte.isdecimal() or len(parte) > 2 for parte in partes):
                raise ValidationError("La selección contiene un horario inválido.")
            dia, hora = map(int, partes)
            if dia not in TurnoPlanilla.DiaSemana.values or hora not in range(23):
                raise ValidationError("La selección contiene un horario inválido.")
            coordenadas.append((dia, time(hora)))
        creados = registrar_turnos_planilla(usuario, cancha, coordenadas)
        messages.success(request, f"Horarios creados: {len(creados)}. Podés asignarles profesores y participantes.")
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    return redirect(_url_planilla(cancha))


@login_required
@never_cache
@require_POST
def planilla_quitar(request):
    usuario = exigir_administracion_clases(request.user)
    cancha_id = request.POST.get("cancha", "")
    if not cancha_id.isdecimal() or len(cancha_id) > 18:
        raise Http404("Elegí una cancha válida de la planilla.")
    cancha = get_object_or_404(Cancha.objects.select_related("sede"), pk=int(cancha_id))
    try:
        identificadores = request.POST.getlist("turno_id")
        firmas = request.POST.getlist("version")
        if not identificadores or len(identificadores) > 161 or len(identificadores) != len(firmas):
            raise ValidationError("Seleccioná los horarios que querés quitar.")
        versiones = {}
        for identificador, firma in zip(identificadores, firmas):
            if not identificador.isdecimal() or len(identificador) > 18 or int(identificador) < 1:
                raise ValidationError("La selección contiene un horario inválido.")
            pk = int(identificador)
            if pk in versiones:
                raise ValidationError("La selección contiene horarios repetidos.")
            versiones[pk] = firma
        cantidad = quitar_turnos_planilla(usuario, cancha, versiones)
        messages.success(request, f"Horarios quitados: {cantidad}. Las clases ya generadas se conservan.")
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    return redirect(_url_planilla(cancha))


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def planilla_formulario(request, pk):
    usuario = exigir_administracion_clases(request.user)
    turno = get_object_or_404(TurnoPlanilla.objects.select_related("cancha__sede"), pk=pk)
    cancha, dia, hora = turno.cancha, turno.dia_semana, turno.hora_inicio
    coordenadas = [(dia, hora)]
    profesores_actuales = list(turno.profesores.values_list("profesor_id", flat=True))
    participantes_actuales = list(turno.alumnos.values_list("usuario_id", flat=True))
    inicial = {
        "observaciones": turno.observaciones,
    }
    url_cancelar = reverse("clases:planilla_detalle", args=[pk])
    if request.method == "POST":
        version = request.POST.get("version", "")
    else:
        version = version_turno_planilla(turno)
    formulario = ObservacionesPlanillaForm(
        request.POST if request.method == "POST" else None, initial=inicial,
    )
    impedimento = None
    try:
        if cancha.estado != Cancha.Estado.ACTIVA or cancha.sede.estado != Sede.Estado.ACTIVA:
            raise ValidationError("La sede y la cancha deben estar activas para guardar la planilla.")
        for dia, hora in coordenadas:
            validar_horario_planilla(cancha.sede, dia, hora)
    except ValidationError as error:
        impedimento = " ".join(error.messages)
    revision = None
    if request.method == "POST" and formulario.is_valid():
        try:
            if impedimento:
                raise ValidationError(impedimento)
            parametros = {
                "profesores_ids": set(profesores_actuales), "participantes_ids": set(participantes_actuales),
                "observaciones": formulario.cleaned_data["observaciones"],
            }
            validar_version_turno_planilla(turno, version)
            datos_revision = {
                "actor": usuario.pk, "turno": pk, "cancha": cancha.pk,
                "horarios": [[dia, hora.isoformat()] for dia, hora in coordenadas],
                "version": version, "profesores": sorted(parametros["profesores_ids"]),
                "participantes": sorted(parametros["participantes_ids"]),
                "observaciones": parametros["observaciones"],
            }
            paso = request.POST.get("paso")
            if paso == "confirmar":
                try:
                    confirmado = signing.loads(request.POST.get("confirmacion", ""), salt="clases.planilla.revision", max_age=900)
                except signing.BadSignature:
                    raise ValidationError("La revisión venció o no es válida. Revisá nuevamente antes de guardar.") from None
                if confirmado != datos_revision:
                    raise ValidationError("Los datos cambiaron. Revisá nuevamente antes de guardar.")
                guardado = editar_turno_planilla(usuario, pk, **parametros, version=version)
                messages.success(request, "El horario de la planilla fue guardado.")
                return redirect("clases:planilla_detalle", pk=guardado.pk)
            if paso == "revisar":
                revision = signing.dumps(datos_revision, salt="clases.planilla.revision", compress=True)
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except TurnoPlanilla.DoesNotExist:
            raise Http404("El horario ya no existe en la planilla.") from None
        except ValidationError as error:
            formulario.add_error(None, error)
    titulo = "Editar observaciones"
    return render(request, "clases/planilla_formulario.html", {
        "titulo": titulo, "editando": True, "formulario": formulario,
        "cancha": cancha, "version": version,
        "horarios": [
            {"dia": TurnoPlanilla.DiaSemana(dia).label, "hora": hora, "hora_fin": time(hora.hour + 1)}
            for dia, hora in coordenadas
        ],
        "revision": revision, "impedimento": impedimento,
        "url_cancelar": url_cancelar,
    })
