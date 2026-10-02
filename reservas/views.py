from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from instalaciones.models import Sede
from usuarios.models import Rol

from .forms import PrecioReservaEstadoForm, PrecioReservaForm
from .models import PrecioReserva


def _exigir_administrador(usuario):
    if not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied


def _informar_duracion_duplicada(formulario, error):
    if error.__cause__.diag.constraint_name != "precio_reserva_sede_duracion_activa_unica":
        raise error
    formulario.add_error(None, "Ya existe una tarifa activa para esa duración en esta sede.")


@login_required
@permission_required("reservas.view_precioreserva", raise_exception=True)
def precio_detalle(request, sede_pk, pk):
    _exigir_administrador(request.user)
    sede = get_object_or_404(Sede, pk=sede_pk)
    precio = get_object_or_404(sede.precios_reservas.all(), pk=pk)
    return render(request, "reservas/precio_detalle.html", {"sede": sede, "precio": precio})


@login_required
@permission_required("reservas.add_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_crear(request, sede_pk):
    _exigir_administrador(request.user)
    sede = get_object_or_404(Sede, pk=sede_pk)
    formulario = PrecioReservaForm(
        request.POST if request.method == "POST" else None,
        sede=sede,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            with transaction.atomic():
                precio = formulario.save()
        except IntegrityError as error:
            _informar_duracion_duplicada(formulario, error)
        else:
            messages.success(request, f'La tarifa "{precio}" fue creada.')
            return redirect("reservas:precio_detalle", sede_pk=sede.pk, pk=precio.pk)

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "sede": sede,
            "formulario": formulario,
            "titulo": "Nuevo precio de reserva",
            "texto_boton": "Crear tarifa",
        },
    )


@login_required
@permission_required("reservas.change_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_editar(request, sede_pk, pk):
    _exigir_administrador(request.user)
    sede = get_object_or_404(Sede, pk=sede_pk)
    with transaction.atomic():
        precios = sede.precios_reservas.all()
        if request.method == "POST":
            precios = precios.select_for_update()
        precio = get_object_or_404(precios, pk=pk)
        formulario = PrecioReservaForm(
            request.POST if request.method == "POST" else None,
            instance=precio,
            sede=sede,
        )
        if request.method == "POST" and formulario.is_valid():
            precio = formulario.save(commit=False)
            precio.save(update_fields=["precio_vigente", "actualizado_en"])
            messages.success(request, f'La tarifa "{precio}" fue actualizada.')
            return redirect("reservas:precio_detalle", sede_pk=sede.pk, pk=precio.pk)

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "sede": sede,
            "formulario": formulario,
            "titulo": "Editar precio de reserva",
            "texto_boton": "Guardar cambios",
            "precio": precio,
        },
    )


@login_required
@permission_required("reservas.change_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_cambiar_estado(request, sede_pk, pk):
    _exigir_administrador(request.user)
    sede = get_object_or_404(Sede, pk=sede_pk)
    with transaction.atomic():
        precios = sede.precios_reservas.all()
        if request.method == "POST":
            precios = precios.select_for_update()
        precio = get_object_or_404(precios, pk=pk)
        nuevo_estado = (
            PrecioReserva.Estado.INACTIVO
            if precio.estado == PrecioReserva.Estado.ACTIVO
            else PrecioReserva.Estado.ACTIVO
        )
        formulario = PrecioReservaEstadoForm(
            request.POST if request.method == "POST" else None,
            initial={"estado": nuevo_estado},
        )
        if request.method == "POST" and formulario.is_valid():
            nuevo_estado = formulario.cleaned_data["estado"]
            precio.estado = nuevo_estado
            try:
                precio.full_clean()
                with transaction.atomic():
                    precio.save(update_fields=["estado", "actualizado_en"])
            except ValidationError as error:
                formulario.add_error(None, error.messages)
            except IntegrityError as error:
                _informar_duracion_duplicada(formulario, error)
            else:
                messages.success(
                    request,
                    f'La tarifa "{precio}" quedó {precio.get_estado_display().lower()}.',
                )
                return redirect("reservas:precio_detalle", sede_pk=sede.pk, pk=precio.pk)

    return render(
        request,
        "reservas/precio_confirmar_cambio_estado.html",
        {
            "sede": sede,
            "precio": precio,
            "nuevo_estado": nuevo_estado,
            "formulario": formulario,
        },
    )
