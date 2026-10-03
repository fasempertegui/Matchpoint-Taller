from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from instalaciones.models import Sede
from usuarios.models import Rol

from .disponibilidad import consultar_disponibilidad
from .forms import DisponibilidadForm, PrecioReservaForm
from .models import PrecioReserva


def _exigir_administrador(usuario):
    if not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied


@login_required
@require_http_methods(["GET", "POST"])
def disponibilidad(request):
    if not request.user.is_active or not request.user.roles.filter(
        rol__codigo__in=(Rol.ADMINISTRADOR, Rol.RESERVAS)
    ).exists():
        raise PermissionDenied

    formulario = DisponibilidadForm(request.POST if request.method == "POST" else None)
    resultado = None
    if request.method == "POST" and formulario.is_valid():
        try:
            resultado = consultar_disponibilidad(
                formulario.cleaned_data["cancha"],
                formulario.cleaned_data["fecha"],
                formulario.cleaned_data["cantidad_horas"],
            )
        except ValidationError as error:
            formulario.add_error(None, error)

    return render(request, "reservas/disponibilidad.html", {
        "formulario": formulario,
        "resultado": resultado,
        "hay_sedes": formulario.fields["sede"].queryset.exists(),
    })


@login_required
@permission_required("reservas.add_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_crear(request, sede_pk):
    _exigir_administrador(request.user)
    formulario = PrecioReservaForm(request.POST if request.method == "POST" else None)
    with transaction.atomic():
        sedes = Sede.objects.all()
        if request.method == "POST":
            # La sede coordina las escrituras incluso cuando todavía no tiene precio.
            sedes = sedes.select_for_update()
        sede = get_object_or_404(sedes, pk=sede_pk)
        precio_activo = sede.precios_reservas.filter(estado=PrecioReserva.Estado.ACTIVO).first()
        if precio_activo and request.method == "GET":
            messages.info(request, "La sede ya tiene un precio activo. Podés actualizarlo.")
            return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#precios")
        if request.method == "POST" and formulario.is_valid():
            if precio_activo:
                formulario.add_error(None, "La sede ya tiene un precio activo. Actualizalo desde la tabla de precios.",)
            else:
                PrecioReserva.objects.create(
                    sede=sede,
                    importe=formulario.cleaned_data["importe"],
                )
                messages.success(request, "El precio por turno fue creado.")
                return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#precios")

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "sede": sede,
            "formulario": formulario,
            "titulo": "Crear precio por turno",
            "texto_boton": "Crear precio",
        },
    )


@login_required
@permission_required("reservas.change_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_actualizar(request, sede_pk, pk):
    _exigir_administrador(request.user)
    with transaction.atomic():
        sedes = Sede.objects.all()
        if request.method == "POST":
            sedes = sedes.select_for_update()
        sede = get_object_or_404(sedes, pk=sede_pk)
        precio = get_object_or_404(sede.precios_reservas.all(), pk=pk)
        if precio.estado != PrecioReserva.Estado.ACTIVO and request.method == "GET":
            messages.info(request, "Los precios inactivos se conservan para consulta. Actualizá el precio activo desde la tabla de precios.",)
            return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#precios")
        formulario = PrecioReservaForm(
            request.POST if request.method == "POST" else None,
            initial={"importe": precio.importe},
        )
        if request.method == "POST" and formulario.is_valid():
            if precio.estado != PrecioReserva.Estado.ACTIVO:
                formulario.add_error(None, "El precio ya fue actualizado. Consultá el precio activo de la sede antes de continuar.",)
            elif formulario.cleaned_data["importe"] == precio.importe:
                formulario.add_error("importe", "El nuevo importe debe ser diferente del precio actual.")
            else:
                precio.estado = PrecioReserva.Estado.INACTIVO
                precio.save(update_fields=["estado", "actualizado_en"])
                PrecioReserva.objects.create(
                    sede=sede,
                    importe=formulario.cleaned_data["importe"],
                )
                messages.success(request, "El precio por turno fue actualizado.")
                return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#precios")

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "sede": sede,
            "formulario": formulario,
            "titulo": "Actualizar precio por turno",
            "texto_boton": "Actualizar precio",
            "precio": precio,
        },
    )
