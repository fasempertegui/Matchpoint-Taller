from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from reservas.forms import PrecioReservaFiltroForm
from reservas.models import Reserva
from usuarios.models import Rol

from .forms import CanchaForm, SedeForm, SedeHorarioForm
from .models import Cancha, Sede, SedeHorario


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
    horarios = {horario.dia_semana: horario for horario in sede.horarios.all()}
    horarios_semana = [
        {"dia": dia, "nombre": nombre, "horario": horarios.get(dia)}
        for dia, nombre in SedeHorario.DiaSemana.choices
    ]
    canchas = sede.canchas.order_by("nombre")
    es_administrador = request.user.tiene_rol(Rol.ADMINISTRADOR)
    puede_consultar_precios = (
        request.user.has_perm("reservas.view_precioreserva")
        and es_administrador
    )
    formulario_precios = None
    precios = None
    precio_activo = False
    if puede_consultar_precios:
        formulario_precios = PrecioReservaFiltroForm(request.GET, prefix="precio")
        precios = sede.precios_reservas.order_by("-creado_en", "-pk")
        precio_activo = precios.filter(estado="activo").exists()
        if formulario_precios.is_valid():
            estado_precio = formulario_precios.cleaned_data["estado"]
            if estado_precio:
                precios = precios.filter(estado=estado_precio)
        else:
            precios = precios.none()
    return render(
        request,
        "instalaciones/sede_detalle.html",
        {
            "sede": sede,
            "canchas": canchas,
            "horarios_semana": horarios_semana,
            "puede_consultar_precios": puede_consultar_precios,
            "formulario_precios": formulario_precios,
            "precios": precios,
            "precio_activo": precio_activo,
            "puede_configurar_horarios": (
                request.user.has_perm("instalaciones.change_sede")
                and es_administrador
            ),
        },
    )


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_horario_configurar(request, pk, dia):
    if not request.user.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    if dia not in SedeHorario.DiaSemana.values:
        raise Http404

    with transaction.atomic():
        sedes = Sede.objects.all()
        if request.method == "POST":
            sedes = sedes.select_for_update()
        sede = get_object_or_404(sedes, pk=pk)
        horario = sede.horarios.filter(dia_semana=dia).first()
        if horario is None:
            horario = SedeHorario(sede=sede, dia_semana=dia)
        formulario = SedeHorarioForm(
            request.POST if request.method == "POST" else None,
            instance=horario,
        )

        if request.method == "POST" and formulario.is_valid():
            if formulario.cleaned_data["hora_inicio_1"] is None:
                sede.horarios.filter(dia_semana=dia).delete()
            else:
                formulario.save()
            sede.save(update_fields=["actualizado_en"])
            messages.success(
                request,
                f'El horario del {horario.get_dia_semana_display().lower()} '
                f'en la sede "{sede.nombre}" fue actualizado.',
            )
            return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#horarios")

    return render(
        request,
        "instalaciones/sede_horario_formulario.html",
        {
            "sede": sede,
            "dia_nombre": horario.get_dia_semana_display(),
            "formulario": formulario,
        },
    )


@login_required
@permission_required("instalaciones.add_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_crear(request):
    formulario = SedeForm(request.POST if request.method == "POST" else None)

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
    formulario = SedeForm(
        request.POST if request.method == "POST" else None,
        instance=sede,
    )

    if request.method == "POST" and formulario.is_valid():
        sede = formulario.save(commit=False)
        sede.save(update_fields=["nombre", "direccion", "observaciones", "actualizado_en"])
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
@require_http_methods(["POST"])
def sede_cambiar_estado(request, pk):
    with transaction.atomic():
        sede = get_object_or_404(Sede.objects.select_for_update(), pk=pk)
        nuevo_estado = request.POST.get("estado")
        if nuevo_estado not in Sede.Estado.values:
            messages.error(request, "El estado solicitado para la sede no es válido.")
            return redirect("instalaciones:sede_detalle", pk=sede.pk)
        if nuevo_estado == sede.estado:
            messages.info(request, f'La sede "{sede.nombre}" ya está {sede.get_estado_display().lower()}.')
            return redirect("instalaciones:sede_detalle", pk=sede.pk)
        if nuevo_estado == Sede.Estado.INACTIVA and Reserva.objects.filter(
            estado=Reserva.Estado.PROGRAMADA,
            detalles__turno__cancha__sede=sede,
        ).exists():
            messages.error(
                request,
                "No se puede desactivar la sede mientras tenga reservas Programadas. "
                "Anulá las futuras o esperá su finalización automática.",
            )
            return redirect("instalaciones:sede_detalle", pk=sede.pk)
        sede.estado = nuevo_estado
        sede.save(update_fields=["estado", "actualizado_en"])
    messages.success(
        request, f'La sede "{sede.nombre}" quedó {sede.get_estado_display().lower()}.'
    )
    return redirect("instalaciones:sede_detalle", pk=sede.pk)


@login_required
@permission_required("instalaciones.add_cancha", raise_exception=True)
@require_http_methods(["GET", "POST"])
def cancha_crear(request, sede_pk):
    sede = get_object_or_404(Sede, pk=sede_pk)
    formulario = CanchaForm(
        request.POST if request.method == "POST" else None,
        sede=sede,
    )

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
    formulario = CanchaForm(
        request.POST if request.method == "POST" else None,
        sede=sede,
        instance=cancha,
    )

    if request.method == "POST" and formulario.is_valid():
        cancha = formulario.save(commit=False)
        cancha.save(update_fields=["nombre", "superficie", "observaciones", "actualizado_en"])
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
    with transaction.atomic():
        sede = get_object_or_404(Sede.objects.select_for_update(), pk=sede_pk)
        cancha = get_object_or_404(Cancha.objects.select_for_update(of=("self",)), pk=pk, sede=sede)
        nuevo_estado = request.POST.get("estado")
        destino = reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#canchas"
        if nuevo_estado not in Cancha.Estado.values:
            messages.error(request, "El estado solicitado para la cancha no es válido.")
            return redirect(destino)
        if nuevo_estado == cancha.estado:
            messages.info(request, f'La cancha "{cancha.nombre}" ya está {cancha.get_estado_display().lower()}.')
            return redirect(destino)
        if nuevo_estado == Cancha.Estado.INACTIVA and Reserva.objects.filter(
            estado=Reserva.Estado.PROGRAMADA,
            detalles__turno__cancha=cancha,
        ).exists():
            messages.error(
                request,
                "No se puede desactivar la cancha mientras tenga reservas Programadas. "
                "Anulá las futuras o esperá su finalización automática.",
            )
            return redirect(destino)
        cancha.estado = nuevo_estado
        cancha.save(update_fields=["estado", "actualizado_en"])
    messages.success(
        request, f'La cancha "{cancha.nombre}" quedó {cancha.get_estado_display().lower()}.'
    )
    return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#canchas")
