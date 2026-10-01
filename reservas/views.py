from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from usuarios.models import Rol

from .forms import PrecioReservaEstadoForm, PrecioReservaFiltroForm, PrecioReservaForm
from .models import PrecioReserva


def _exigir_administrador(usuario):
    if not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied


def _informar_duracion_duplicada(formulario, error):
    if error.__cause__.diag.constraint_name != "precio_reserva_duracion_activa_unica":
        raise error
    formulario.add_error(None, "Ya existe una tarifa activa para esa duración.")


@login_required
@permission_required("reservas.view_precioreserva", raise_exception=True)
def precio_lista(request):
    _exigir_administrador(request.user)
    formulario = PrecioReservaFiltroForm(request.GET)
    precios = PrecioReserva.objects.all()
    if formulario.is_valid():
        estado = formulario.cleaned_data["estado"]
        duracion = formulario.cleaned_data["duracion_horas"]
        if estado:
            precios = precios.filter(estado=estado)
        if duracion is not None:
            precios = precios.filter(duracion_horas=duracion)
    else:
        precios = precios.none()
    return render(
        request,
        "reservas/precio_lista.html",
        {"precios": precios, "formulario": formulario},
    )


@login_required
@permission_required("reservas.view_precioreserva", raise_exception=True)
def precio_detalle(request, pk):
    _exigir_administrador(request.user)
    precio = get_object_or_404(PrecioReserva, pk=pk)
    return render(request, "reservas/precio_detalle.html", {"precio": precio})


@login_required
@permission_required("reservas.add_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_crear(request):
    _exigir_administrador(request.user)
    formulario = PrecioReservaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and formulario.is_valid():
        try:
            with transaction.atomic():
                precio = formulario.save()
        except IntegrityError as error:
            _informar_duracion_duplicada(formulario, error)
        else:
            messages.success(request, f'La tarifa "{precio}" fue creada.')
            return redirect("reservas:precio_detalle", pk=precio.pk)

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "formulario": formulario,
            "titulo": "Nuevo precio de reserva",
            "texto_boton": "Crear tarifa",
        },
    )


@login_required
@permission_required("reservas.change_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_editar(request, pk):
    _exigir_administrador(request.user)
    with transaction.atomic():
        precios = PrecioReserva.objects.all()
        if request.method == "POST":
            precios = precios.select_for_update()
        precio = get_object_or_404(precios, pk=pk)
        formulario = PrecioReservaForm(
            request.POST if request.method == "POST" else None,
            instance=precio,
        )
        if request.method == "POST" and formulario.is_valid():
            precio = formulario.save(commit=False)
            precio.save(update_fields=["precio_vigente", "actualizado_en"])
            messages.success(request, f'La tarifa "{precio}" fue actualizada.')
            return redirect("reservas:precio_detalle", pk=precio.pk)

    return render(
        request,
        "reservas/precio_formulario.html",
        {
            "formulario": formulario,
            "titulo": "Editar precio de reserva",
            "texto_boton": "Guardar cambios",
            "precio": precio,
        },
    )


@login_required
@permission_required("reservas.change_precioreserva", raise_exception=True)
@require_http_methods(["GET", "POST"])
def precio_cambiar_estado(request, pk):
    _exigir_administrador(request.user)
    with transaction.atomic():
        precios = PrecioReserva.objects.all()
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
                return redirect("reservas:precio_detalle", pk=precio.pk)

    return render(
        request,
        "reservas/precio_confirmar_cambio_estado.html",
        {"precio": precio, "nuevo_estado": nuevo_estado, "formulario": formulario},
    )
