from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import CanchaForm, SedeForm
from .models import Cancha, Sede


@login_required
@permission_required("instalaciones.view_sede", raise_exception=True)
def sede_lista(request):
    sedes = Sede.objects.all()
    estado = request.GET.get("estado", "")
    if estado in Sede.Estado.values:
        sedes = sedes.filter(estado=estado)
    else:
        estado = ""
    return render(
        request,
        "instalaciones/sede_lista.html",
        {"sedes": sedes, "estados": Sede.Estado.choices, "estado_actual": estado},
    )


@login_required
@permission_required("instalaciones.view_sede", raise_exception=True)
def sede_detalle(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    canchas = sede.canchas.all()
    estado_cancha = request.GET.get("estado_cancha", "")
    if estado_cancha in Cancha.Estado.values:
        canchas = canchas.filter(estado=estado_cancha)
    else:
        estado_cancha = ""
    return render(
        request,
        "instalaciones/sede_detalle.html",
        {
            "sede": sede,
            "canchas": canchas,
            "estados_cancha": Cancha.Estado.choices,
            "estado_cancha_actual": estado_cancha,
        },
    )


@login_required
@permission_required("instalaciones.add_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_crear(request):
    formulario = SedeForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        sede = formulario.save()
        messages.success(request, f'La sede "{sede.nombre}" fue creada.')
        return redirect("instalaciones:sede_lista")

    return render(
        request,
        "instalaciones/sede_formulario.html",
        {
            "formulario": formulario,
            "titulo": "Nueva sede",
            "texto_boton": "Crear sede",
        },
    )


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_editar(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    formulario = SedeForm(request.POST or None, instance=sede)

    if request.method == "POST" and formulario.is_valid():
        sede = formulario.save()
        messages.success(request, f'La sede "{sede.nombre}" fue actualizada.')
        return redirect("instalaciones:sede_lista")

    return render(
        request,
        "instalaciones/sede_formulario.html",
        {
            "formulario": formulario,
            "titulo": f"Editar {sede.nombre}",
            "texto_boton": "Guardar cambios",
            "sede": sede,
        },
    )


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_cambiar_estado(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    nuevo_estado = (
        Sede.Estado.INACTIVA if sede.estado == Sede.Estado.ACTIVA else Sede.Estado.ACTIVA
    )

    if request.method == "POST":
        sede.estado = nuevo_estado
        sede.save(update_fields=["estado", "actualizado_en"])
        messages.success(
            request, f'La sede "{sede.nombre}" quedó {sede.get_estado_display().lower()}.'
        )
        return redirect("instalaciones:sede_detalle", pk=sede.pk)

    return render(
        request,
        "instalaciones/sede_confirmar_cambio_estado.html",
        {"sede": sede, "nuevo_estado": nuevo_estado},
    )


@login_required
@permission_required("instalaciones.add_cancha", raise_exception=True)
@require_http_methods(["GET", "POST"])
def cancha_crear(request, sede_pk):
    sede = get_object_or_404(Sede, pk=sede_pk)
    formulario = CanchaForm(request.POST or None, sede=sede)

    if request.method == "POST" and formulario.is_valid():
        cancha = formulario.save()
        messages.success(request, f'La cancha "{cancha.nombre}" fue creada.')
        return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#canchas")

    return render(
        request,
        "instalaciones/cancha_formulario.html",
        {
            "formulario": formulario,
            "sede": sede,
            "titulo": f"Nueva cancha en {sede.nombre}",
            "texto_boton": "Crear cancha",
        },
    )


@login_required
@permission_required("instalaciones.change_cancha", raise_exception=True)
@require_http_methods(["GET", "POST"])
def cancha_editar(request, sede_pk, pk):
    sede = get_object_or_404(Sede, pk=sede_pk)
    cancha = get_object_or_404(Cancha, pk=pk, sede=sede)
    formulario = CanchaForm(request.POST or None, sede=sede, instance=cancha)

    if request.method == "POST" and formulario.is_valid():
        cancha = formulario.save()
        messages.success(request, f'La cancha "{cancha.nombre}" fue actualizada.')
        return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#canchas")

    return render(
        request,
        "instalaciones/cancha_formulario.html",
        {
            "formulario": formulario,
            "sede": sede,
            "cancha": cancha,
            "titulo": f"Editar {cancha.nombre}",
            "texto_boton": "Guardar cambios",
        },
    )


@login_required
@permission_required("instalaciones.change_cancha", raise_exception=True)
@require_http_methods(["POST"])
def cancha_cambiar_estado(request, sede_pk, pk):
    sede = get_object_or_404(Sede, pk=sede_pk)
    cancha = get_object_or_404(Cancha, pk=pk, sede=sede)
    cancha.estado = (
        Cancha.Estado.INACTIVA if cancha.estado == Cancha.Estado.ACTIVA else Cancha.Estado.ACTIVA
    )
    cancha.save(update_fields=["estado", "actualizado_en"])
    messages.success(
        request, f'La cancha "{cancha.nombre}" quedó {cancha.get_estado_display().lower()}.'
    )
    return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#canchas")
