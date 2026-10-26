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
from django.views.decorators.http import require_GET, require_http_methods

from instalaciones.models import Cancha, Sede

from .forms import PlanillaFiltroForm, PlanillaForm
from .models import TurnoPlanilla
from .permisos import exigir_administracion_clases
from .planilla import (
    consultar_planilla, editar_turno_planilla, quitar_turno_planilla,
    registrar_turnos_planilla, validar_version_turno_planilla, version_turno_planilla,
)
from .validaciones import validar_horario_planilla, validar_usuarios_clase


def _url_planilla(cancha):
    return reverse("clases:planilla") + "?" + urlencode({"sede": cancha.sede_id, "cancha": cancha.pk})


def _breadcrumbs(titulo=None, cancha=None):
    items = [("Inicio", reverse("inicio")), ("Planilla semanal", _url_planilla(cancha) if cancha else None)]
    if titulo:
        items.append((titulo, None))
    return items


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
                        turno["modalidad_texto"] = dict(TurnoPlanilla.Modalidad.choices).get(turno["modalidad"], "Sin especificar")
                    seleccionable = not turno and habilitada and cancha.estado == Cancha.Estado.ACTIVA and cancha.sede.estado == Sede.Estado.ACTIVA
                    celdas.append({
                        "turno": turno, "habilitada": habilitada, "url": url, "dia": nombre,
                        "numero_dia": dia, "seleccionable": seleccionable,
                    })
                filas.append({"hora": time(hora), "celdas": celdas, "seleccionable": any(c["seleccionable"] for c in celdas)})
    return render(request, "clases/planilla.html", {
        "formulario": formulario, "hay_sedes": sede is not None,
        "datos": datos, "cancha": cancha, "filas": filas,
        "dias": TurnoPlanilla.DiaSemana.labels, "breadcrumbs": _breadcrumbs(),
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
        "breadcrumbs": _breadcrumbs("Horario habitual", turno.cancha),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def planilla_formulario(request, pk=None):
    usuario = exigir_administracion_clases(request.user)
    turno = None
    inicial = {}
    profesores_actuales = []
    participantes_actuales = []
    if pk is not None:
        turno = get_object_or_404(TurnoPlanilla.objects.select_related("cancha__sede"), pk=pk)
        cancha, dia, hora = turno.cancha, turno.dia_semana, turno.hora_inicio
        coordenadas = [(dia, hora)]
        profesores_actuales = list(turno.profesores.values_list("profesor_id", flat=True))
        participantes_actuales = list(turno.alumnos.values_list("usuario_id", flat=True))
        inicial = {
            "profesores": profesores_actuales, "participantes": participantes_actuales,
            "modalidad": turno.modalidad or "", "observaciones": turno.observaciones,
        }
    else:
        cancha_id = request.GET.get("cancha", "")
        valores = request.GET.getlist("turno")
        if not cancha_id.isdecimal() or len(cancha_id) > 18 or not valores or len(valores) > 161:
            raise Http404("Elegí un horario de la planilla.")
        coordenadas = []
        for valor in valores:
            partes = valor.split("-")
            if len(partes) != 2 or any(not parte.isdecimal() or len(parte) > 2 for parte in partes):
                raise Http404("Elegí un horario válido de la planilla.")
            dia, numero_hora = map(int, partes)
            if dia not in TurnoPlanilla.DiaSemana.values or numero_hora not in range(23):
                raise Http404("Elegí un horario válido de la planilla.")
            coordenadas.append((dia, time(numero_hora)))
        coordenadas = sorted(set(coordenadas))
        cancha = get_object_or_404(Cancha.objects.select_related("sede"), pk=int(cancha_id))
    url_cancelar = reverse("clases:planilla_detalle", args=[pk]) if turno else _url_planilla(cancha)
    if request.method == "POST":
        version = request.POST.get("version", "")
    else:
        version = version_turno_planilla(turno) if turno else ""
    formulario = PlanillaForm(
        request.POST if request.method == "POST" else None, initial=inicial,
        profesores_actuales=profesores_actuales, participantes_actuales=participantes_actuales,
    )
    impedimento = None
    try:
        if cancha.estado != Cancha.Estado.ACTIVA or cancha.sede.estado != Sede.Estado.ACTIVA:
            raise ValidationError("La sede y la cancha deben estar activas para guardar la planilla.")
        ocupados = set(TurnoPlanilla.objects.filter(cancha=cancha).values_list("dia_semana", "hora_inicio")) if not turno else set()
        for dia, hora in coordenadas:
            validar_horario_planilla(cancha.sede, dia, hora)
            if (dia, hora) in ocupados:
                raise ValidationError("Ya existe un turno de planilla para esa cancha, día y hora.")
    except ValidationError as error:
        impedimento = " ".join(error.messages)
    revision = None
    advertencias = []
    if request.method == "POST" and formulario.is_valid():
        try:
            if impedimento:
                raise ValidationError(impedimento)
            parametros = formulario.parametros()
            personas = {
                persona.pk: persona for persona in list(formulario.cleaned_data["profesores"].prefetch_related("roles__rol"))
                + list(formulario.cleaned_data["participantes"].prefetch_related("roles__rol"))
            }
            validar_usuarios_clase(personas, parametros["profesores_ids"], parametros["participantes_ids"], requiere_profesor=False)
            if turno:
                validar_version_turno_planilla(turno, version)
            cantidad = len(parametros["participantes_ids"])
            if parametros["modalidad"] == "grupal" and cantidad > 6:
                advertencias.append("Superás el máximo recomendado de 6 participantes para una clase grupal.")
            elif parametros["modalidad"] == "individual" and cantidad > 1:
                advertencias.append(f"La clase individual tiene {cantidad} participantes. Podés continuar si está acordado.")
            datos_revision = {
                "actor": usuario.pk, "turno": pk, "cancha": cancha.pk,
                "horarios": [[dia, hora.isoformat()] for dia, hora in coordenadas],
                "version": version, "profesores": sorted(parametros["profesores_ids"]),
                "participantes": sorted(parametros["participantes_ids"]),
                "modalidad": parametros["modalidad"], "observaciones": parametros["observaciones"],
            }
            paso = request.POST.get("paso")
            if paso == "confirmar":
                try:
                    confirmado = signing.loads(request.POST.get("confirmacion", ""), salt="clases.planilla.revision", max_age=900)
                except signing.BadSignature:
                    raise ValidationError("La revisión venció o no es válida. Revisá nuevamente antes de guardar.") from None
                if confirmado != datos_revision:
                    raise ValidationError("Los datos cambiaron. Revisá nuevamente antes de guardar.")
                if turno:
                    guardado = editar_turno_planilla(usuario, pk, **parametros, version=version)
                else:
                    registrar_turnos_planilla(usuario, cancha, coordenadas, **parametros)
                    messages.success(request, "El horario de la planilla fue guardado.")
                    return redirect(_url_planilla(cancha))
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
    titulo = "Editar horario habitual" if turno else "Agregar horario habitual"
    return render(request, "clases/planilla_formulario.html", {
        "titulo": titulo, "editando": turno is not None, "formulario": formulario,
        "cancha": cancha, "version": version,
        "horarios": [
            {"dia": TurnoPlanilla.DiaSemana(dia).label, "hora": hora, "hora_fin": time(hora.hour + 1)}
            for dia, hora in coordenadas
        ],
        "revision": revision, "advertencias": advertencias, "impedimento": impedimento,
        "profesores": formulario.seleccionados("profesores"),
        "participantes": formulario.seleccionados("participantes"),
        "modalidad_texto": dict(formulario.fields["modalidad"].choices).get(formulario["modalidad"].value(), "Sin especificar"),
        "url_cancelar": url_cancelar, "breadcrumbs": _breadcrumbs(titulo, cancha),
    })
