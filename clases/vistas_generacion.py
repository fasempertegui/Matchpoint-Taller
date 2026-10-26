from datetime import date, time
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from instalaciones.models import Cancha, Sede
from reservas.models import Evento
from usuarios.models import Usuario

from .forms import GeneracionClasesForm
from .generacion import (
    confirmar_generacion, confirmar_regeneracion, generar_clases,
    preparar_generacion, preparar_regeneracion, regenerar_clases,
)
from .models import Clase, TurnoPlanilla
from .permisos import exigir_administracion_clases
from .servicios import eliminar_clase_generada, preparar_eliminacion_clase


def _url_planilla(sede, cancha_id=None):
    parametros = {"sede": sede.pk} if sede else {}
    if sede and cancha_id and str(cancha_id).isdecimal() and len(str(cancha_id)) < 19:
        if Cancha.objects.filter(pk=cancha_id, sede=sede).exists():
            parametros["cancha"] = cancha_id
    url = reverse("clases:planilla")
    return url + "?" + urlencode(parametros) if parametros else url


def _filas_revision(filas):
    canchas = Cancha.objects.in_bulk({fila["cancha_id"] for fila in filas})
    usuarios_ids = {pk for fila in filas for pk in fila["profesores_ids"] + fila["participantes_ids"]}
    usuarios = Usuario.objects.in_bulk(usuarios_ids)
    return [
        {
            **fila, "cancha": canchas[fila["cancha_id"]],
            "hora_fin": time(fila["hora_inicio"].hour + 1),
            "modalidad_texto": dict(TurnoPlanilla.Modalidad.choices).get(fila["modalidad"], "Sin especificar"),
            "profesores": [str(usuarios[pk]) for pk in fila["profesores_ids"]],
            "participantes": [str(usuarios[pk]) for pk in fila["participantes_ids"]],
            "advertencia": fila["modalidad"] == TurnoPlanilla.Modalidad.GRUPAL and len(fila["participantes_ids"]) > 6,
        }
        for fila in filas
    ]


def _filas_clases_existentes(filas):
    canchas = Cancha.objects.in_bulk({fila["cancha_id"] for fila in filas})
    return [
        {
            **fila, "cancha": canchas[fila["cancha_id"]],
            "hora_fin": time(fila["hora_inicio"].hour + 1),
            "estado": fila.get("estado", Evento.Estado.PROGRAMADO),
            "estado_texto": Evento.Estado(fila.get("estado", Evento.Estado.PROGRAMADO)).label,
        }
        for fila in filas
    ]


def _validar_alcance_confirmacion(token, usuario, datos, operacion):
    try:
        firmado = signing.loads(token, salt="clases.generacion", max_age=900)
    except signing.BadSignature:
        raise ValidationError("La revisión venció o no es válida. Revisá nuevamente la generación.") from None
    if (
        firmado.get("usuario") != usuario.pk or firmado.get("operacion") != operacion
        or firmado.get("sede") != datos["sede"].pk
        or firmado.get("desde") != datos["fecha_desde"].isoformat()
        or firmado.get("hasta") != datos["fecha_hasta"].isoformat()
    ):
        raise ValidationError("Los datos cambiaron. Revisá nuevamente la generación.")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def generacion_clases(request, regenerar=False):
    operacion = "regenerar" if regenerar else "generar"
    titulo = "Regenerar clases" if regenerar else "Generar clases"
    preparar = preparar_regeneracion if regenerar else preparar_generacion
    confirmar = confirmar_regeneracion if regenerar else confirmar_generacion
    ejecutar = regenerar_clases if regenerar else generar_clases
    usuario = exigir_administracion_clases(request.user)
    formulario = GeneracionClasesForm(
        request.POST if request.method == "POST" else None,
        initial={"sede": request.GET.get("sede"), "fecha_desde": timezone.localdate(), "fecha_hasta": timezone.localdate()},
    )
    revision = None
    confirmacion_final = False
    candidatas = []
    omitidas = []
    sede = None
    reemplazos = []
    conservadas = []
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        sede = datos["sede"]
        paso = request.POST.get("paso")
        try:
            if paso in ("confirmar_revision", "generar"):
                _validar_alcance_confirmacion(request.POST.get("confirmacion", ""), usuario, datos, operacion)
            if paso == "generar":
                resultado = ejecutar(usuario, request.POST.get("confirmacion", ""))
                request.session["resultado_generacion_clases"] = {
                    "operacion": operacion,
                    "reemplazadas": resultado["clases_reemplazadas"],
                    "conservadas_ids": resultado["clases_conservadas_ids"],
                    "sede": sede.pk, "desde": datos["fecha_desde"].isoformat(), "hasta": datos["fecha_hasta"].isoformat(),
                    "clases_ids": resultado["clases_ids"], "omitidas": len(resultado["omitidas"]),
                    "detalle_omitidas": [
                        {**fila, "fecha": fila["fecha"].isoformat(), "hora_inicio": fila["hora_inicio"].isoformat()}
                        for fila in resultado["omitidas"]
                    ],
                    "cancha": request.GET.get("cancha"),
                }
                return redirect("clases:generacion_resultado")
            if paso == "confirmar_revision":
                revision = confirmar(usuario, request.POST.get("confirmacion", ""))
                confirmacion_final = True
            elif paso == "revisar":
                revision = preparar(usuario, sede.pk, datos["fecha_desde"], datos["fecha_hasta"])
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
            if revision:
                candidatas = _filas_revision(revision["candidatas"])
                omitidas = _filas_revision(revision["omitidas"])
                reemplazos = _filas_clases_existentes(revision["reemplazos"])
                conservadas = _filas_clases_existentes(revision["conservadas"])
        except Sede.DoesNotExist:
            formulario.add_error(None, "La sede ya no está disponible. Revisá nuevamente la generación.")
            revision = None
        except ValidationError as error:
            formulario.add_error(None, error)
            revision = None
    if sede is None:
        valor = formulario["sede"].value()
        if valor and str(valor).isdecimal() and len(str(valor)) < 19:
            sede = Sede.objects.filter(pk=valor).first()
    url_planilla = _url_planilla(sede, request.GET.get("cancha"))
    return render(request, "clases/generacion_formulario.html", {
        "formulario": formulario, "revision": revision, "confirmacion_final": confirmacion_final,
        "regenerar": regenerar, "titulo": titulo, "reemplazos": reemplazos, "conservadas": conservadas,
        "hay_cambios": bool(candidatas or reemplazos),
        "candidatas": candidatas, "omitidas": omitidas, "sede": sede, "url_planilla": url_planilla,
        "hay_advertencias": any(fila["advertencia"] for fila in candidatas),
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Planilla semanal", url_planilla), (titulo, None)],
    })


@login_required
@never_cache
@require_GET
def generacion_resultado(request):
    exigir_administracion_clases(request.user)
    resultado = request.session.get("resultado_generacion_clases")
    if not resultado:
        return redirect("clases:planilla")
    sede = Sede.objects.filter(pk=resultado["sede"]).first()
    clases = Clase.objects.filter(pk__in=resultado["clases_ids"]).select_related(
        "evento__turno__cancha__sede",
    ).order_by("evento__turno__fecha", "evento__turno__hora_inicio", "evento__turno__cancha_id", "pk")
    pagina = Paginator(clases, 10).get_page(request.GET.get("pagina"))
    omitidas = _filas_revision([
        {**fila, "fecha": date.fromisoformat(fila["fecha"]), "hora_inicio": time.fromisoformat(fila["hora_inicio"])}
        for fila in resultado["detalle_omitidas"]
    ])
    conservadas = _filas_clases_existentes([
        {"id": clase.pk, "fecha": clase.evento.turno.fecha, "hora_inicio": clase.evento.turno.hora_inicio,
         "cancha_id": clase.evento.turno.cancha_id, "estado": clase.evento.estado}
        for clase in Clase.objects.filter(pk__in=resultado.get("conservadas_ids", [])).select_related("evento__turno").order_by(
            "evento__turno__fecha", "evento__turno__hora_inicio", "evento__turno__cancha_id", "pk",
        )
    ])
    regenerar = resultado.get("operacion", "generar") == "regenerar"
    titulo = "Resultado de regeneración" if regenerar else "Resultado de generación"
    return render(request, "clases/generacion_resultado.html", {
        "resultado": resultado, "cantidad_creadas": len(resultado["clases_ids"]), "sede": sede,
        "regenerar": regenerar, "titulo": titulo, "conservadas": conservadas,
        "desde": date.fromisoformat(resultado["desde"]), "hasta": date.fromisoformat(resultado["hasta"]),
        "pagina": pagina, "omitidas": omitidas, "url_planilla": _url_planilla(sede, resultado.get("cancha")),
        "url_agenda": reverse("agenda:agenda") + "?" + urlencode({"sede": resultado["sede"], "fecha": resultado["desde"]}),
        "breadcrumbs": [("Inicio", reverse("inicio")), ("Planilla semanal", _url_planilla(sede)), (titulo, None)],
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def clase_eliminar(request, pk):
    usuario = exigir_administracion_clases(request.user)
    clase = get_object_or_404(Clase.objects.select_related("evento__turno__cancha__sede"), pk=pk)
    turno = clase.evento.turno
    url_detalle = reverse("clases:clase_detalle", args=[pk])
    url_agenda = reverse("agenda:agenda") + "?" + urlencode({
        "sede": turno.cancha.sede_id, "cancha": turno.cancha_id,
        "fecha": turno.fecha.isoformat(), "hora": turno.hora_inicio.hour,
    })
    try:
        if request.method == "POST":
            if request.POST.get("paso") != "confirmar":
                raise ValidationError("La acción solicitada no es válida.")
            token = request.POST.get("confirmacion", "")
            try:
                signing.loads(token, salt="clases.eliminacion", max_age=900)
            except signing.BadSignature:
                raise ValidationError("La revisión venció o no es válida. Revisá nuevamente la eliminación.") from None
            eliminar_clase_generada(usuario, pk, token)
            messages.success(request, "La clase generada fue eliminada. El turno quedó libre.")
            return redirect(url_agenda)
        revision = preparar_eliminacion_clase(usuario, pk)
    except Clase.DoesNotExist:
        messages.info(request, "La clase ya no existe.")
        return redirect(url_agenda)
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect(url_detalle)
    return render(request, "clases/clase_eliminar.html", {
        "clase": clase, "turno": turno, "revision": revision, "url_detalle": url_detalle,
        "breadcrumbs": [("Inicio", reverse("inicio")), (f"Clase {pk}", url_detalle), ("Eliminar clase generada", None)],
    })
