from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from common.fechas import FECHA_INICIO_OPERACIONES
from instalaciones.models import Sede
from membresias.fechas import meses_contratables
from membresias.models import PlanUsuario
from usuarios.models import Rol

from .forms import SeguimientoContratacionesForm
from .models import TurnoPlanillaAlumno
from .permisos import exigir_administracion_clases


@login_required
@never_cache
@require_GET
def seguimiento_contrataciones(request):
    exigir_administracion_clases(request.user)
    parametros = request.GET.copy()
    sede = Sede.objects.order_by("estado", "nombre", "pk").first()
    if sede:
        parametros.setdefault("sede", str(sede.pk))
    parametros.setdefault("mes", timezone.localdate().replace(day=1).isoformat())
    formulario = SeguimientoContratacionesForm(parametros)
    cancha_inicial = formulario.fields["cancha"].queryset.first()
    if cancha_inicial:
        parametros.setdefault("cancha", str(cancha_inicial.pk))
        formulario = SeguimientoContratacionesForm(parametros)
    contexto = {"formulario": formulario, "hay_sedes": sede is not None}
    if sede and formulario.is_valid():
        cancha = formulario.cleaned_data["cancha"]
        mes = formulario.cleaned_data["mes"]
        anterior = (mes - timedelta(days=1)).replace(day=1)
        if anterior < FECHA_INICIO_OPERACIONES:
            anterior = None
        personas = {}
        asignaciones = TurnoPlanillaAlumno.objects.filter(turno_planilla__cancha=cancha).select_related(
            "usuario", "turno_planilla",
        ).prefetch_related("usuario__roles__rol").order_by(
            "usuario__last_name", "usuario__first_name", "usuario__username",
            "turno_planilla__dia_semana", "turno_planilla__hora_inicio",
        )
        for asignacion in asignaciones:
            fila = personas.setdefault(asignacion.usuario_id, {"usuario": asignacion.usuario, "horarios": []})
            fila["horarios"].append(asignacion.turno_planilla)
        contratos = {
            (contrato.usuario_id, contrato.mes_cubierto): contrato
            for contrato in PlanUsuario.objects.filter(
                usuario_id__in=personas, mes_cubierto__in=[periodo for periodo in (mes, anterior) if periodo],
            ).exclude(estado=PlanUsuario.Estado.ANULADO).select_related("plan")
        }
        filas = []
        sin_contratacion = 0
        terminos = formulario.cleaned_data["q"].casefold().split()
        mes_habilitado = mes in meses_contratables()
        for usuario_id, fila in personas.items():
            contrato = contratos.get((usuario_id, mes))
            previo = contratos.get((usuario_id, anterior))
            sin_contratacion += contrato is None
            nombre = f'{fila["usuario"]} {fila["usuario"].username}'.casefold()
            if any(termino not in nombre for termino in terminos):
                continue
            if formulario.cleaned_data["solo_sin"] and contrato is not None:
                continue
            usuario = fila["usuario"]
            puede_registrar = mes_habilitado and usuario.esta_habilitado and not any(
                vinculo.rol.codigo == Rol.PROFESOR for vinculo in usuario.roles.all()
            )
            fila.update({
                "contrato": contrato, "anterior": previo,
                "producto_distinto": contrato is not None and previo is not None and contrato.plan_id != previo.plan_id,
                "url_alta": reverse("membresias:contratacion_plan_crear") + "?" + urlencode({
                    "usuario": usuario_id, "mes_cubierto": mes.isoformat(),
                }) if puede_registrar else None,
            })
            filas.append(fila)
        consulta = request.GET.copy()
        consulta.pop("pagina", None)
        consulta["sede"] = str(cancha.sede_id)
        consulta["cancha"] = str(cancha.pk)
        consulta["mes"] = mes.isoformat()
        contexto.update({
            "cancha": cancha, "mes": mes, "mes_anterior": anterior,
            "pagina": Paginator(filas, 25).get_page(request.GET.get("pagina")),
            "total_personas": len(personas), "sin_contratacion": sin_contratacion,
            "consulta": consulta.urlencode(),
            "url_planilla": reverse("clases:planilla") + "?" + urlencode({"sede": cancha.sede_id, "cancha": cancha.pk}),
        })
    return render(request, "clases/seguimiento_contrataciones.html", contexto)
