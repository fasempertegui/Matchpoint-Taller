from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from reservas.models import Evento
from usuarios.models import Usuario

from .consultas import consultar_clase
from .models import Asistencia, Clase, TurnoPlanilla


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

    url_agenda = reverse("agenda:agenda") + "?" + urlencode({
        "sede": clase["sede"]["id"],
        "cancha": clase["cancha"]["id"],
        "fecha": clase["fecha"].isoformat(),
        "hora": clase["hora_inicio"].hour,
    })
    return render(request, "clases/clase_detalle.html", {
        "clase": clase,
        "puede_consultar_grupo": puede_consultar_grupo,
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
