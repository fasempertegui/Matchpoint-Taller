from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import prefetch_related_objects
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .feriados import consultar_feriados, preparar_feriado, quitar_feriado, registrar_feriado
from .forms import FeriadoForm
from .models import ClaseAlumno, ClaseProfesor, Feriado
from .permisos import exigir_administracion_clases


def _breadcrumbs(titulo=None):
    items = [("Inicio", reverse("inicio")), ("Feriados", reverse("clases:feriado_lista") if titulo else None)]
    if titulo:
        items.append((titulo, None))
    return items


@login_required
@never_cache
@require_GET
def feriado_lista(request):
    usuario = exigir_administracion_clases(request.user)
    pagina = Paginator(consultar_feriados(usuario), 10).get_page(request.GET.get("pagina"))
    return render(request, "clases/feriado_lista.html", {
        "pagina": pagina, "breadcrumbs": _breadcrumbs(),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def feriado_registrar(request):
    usuario = exigir_administracion_clases(request.user)
    formulario = FeriadoForm(
        request.POST if request.method == "POST" else None,
        initial={"fecha": timezone.localdate()},
    )
    revision = None
    clases = []
    if request.method == "POST" and formulario.is_valid():
        try:
            paso = request.POST.get("paso")
            if paso == "confirmar":
                feriado = registrar_feriado(
                    usuario, **formulario.cleaned_data, confirmacion=request.POST.get("confirmacion", ""),
                )
                messages.success(request, "El feriado fue registrado.")
                return redirect("clases:feriado_detalle", pk=feriado.pk)
            if paso == "revisar":
                revision = preparar_feriado(usuario, **formulario.cleaned_data)
                prefetch_related_objects(
                    revision["clases"], "evento__turno__cancha__sede", "profesores__profesor", "alumnos__usuario",
                )
                for clase in revision["clases"]:
                    turno = clase.evento.turno
                    clases.append({
                        "id": clase.pk, "sede": turno.cancha.sede.nombre, "cancha": turno.cancha.nombre,
                        "hora": turno.hora_inicio, "hora_fin": turno.hora_fin,
                        "profesores": [v.profesor for v in clase.profesores.all() if v.estado == ClaseProfesor.Estado.ACTIVO],
                        "participantes": [v.usuario for v in clase.alumnos.all() if v.estado == ClaseAlumno.Estado.ACTIVO],
                    })
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)
    return render(request, "clases/feriado_formulario.html", {
        "formulario": formulario, "revision": revision, "clases": clases,
        "breadcrumbs": _breadcrumbs("Registrar feriado"),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def feriado_detalle(request, pk):
    usuario = exigir_administracion_clases(request.user)
    feriado = get_object_or_404(Feriado, pk=pk)
    if request.method == "POST":
        try:
            if request.POST.get("accion") != "quitar":
                raise ValidationError("La acción solicitada no es válida.")
            quitar_feriado(usuario, pk)
            messages.success(request, "El feriado fue quitado. Las clases Anuladas no se reactivan.")
            return redirect("clases:feriado_lista")
        except Feriado.DoesNotExist:
            messages.info(request, "El feriado ya no está registrado.")
            return redirect("clases:feriado_lista")
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)
            return redirect("clases:feriado_detalle", pk=pk)
    return render(request, "clases/feriado_detalle.html", {
        "feriado": feriado, "breadcrumbs": _breadcrumbs("Detalle de feriado"),
    })
