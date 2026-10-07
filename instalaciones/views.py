from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from psycopg.errors import UniqueViolation

from reservas.models import Evento
from usuarios.models import Rol

from .forms import CanchaForm, SedeForm, SedeHorarioForm, SedePrecioForm
from .models import Cancha, Sede, SedeHorario


def _breadcrumbs_sede(usuario, sede=None, pestana=None):
    puede_consultar = usuario.has_perm("instalaciones.view_sede")
    breadcrumbs = [
        ("Inicio", reverse("inicio")),
        ("Sedes", reverse("instalaciones:sede_lista") if puede_consultar else None),
    ]
    if sede is not None:
        enlace = reverse("instalaciones:sede_detalle", args=[sede.pk])
        if pestana:
            enlace += "#" + pestana
        breadcrumbs.append((sede.nombre, enlace if puede_consultar else None))
    return breadcrumbs


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
        {
            "sedes": sedes,
            "estados": Sede.Estado.choices,
            "estado_actual": estado,
            "breadcrumbs": _breadcrumbs_sede(request.user),
        },
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
    return render(
        request,
        "instalaciones/sede_detalle.html",
        {
            "sede": sede,
            "breadcrumbs": _breadcrumbs_sede(request.user, sede),
            "canchas": canchas,
            "horarios_semana": horarios_semana,
            "puede_consultar_precio": es_administrador,
            "puede_configurar_precio": (
                request.user.has_perm("instalaciones.change_sede")
                and es_administrador
            ),
            "puede_configurar_horarios": (
                request.user.has_perm("instalaciones.change_sede")
                and es_administrador
            ),
        },
    )


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_precio_configurar(request, pk):
    if not request.user.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied

    with transaction.atomic():
        sedes = Sede.objects.all()
        if request.method == "POST":
            sedes = sedes.select_for_update()
        sede = get_object_or_404(sedes, pk=pk)
        precio_actual = sede.precio_reserva_vigente
        formulario = SedePrecioForm(
            request.POST if request.method == "POST" else None,
            instance=sede,
        )

        if request.method == "POST" and formulario.is_valid():
            if formulario.cleaned_data["precio_mostrado"] != precio_actual:
                datos = request.POST.copy()
                datos["precio_mostrado"] = str(precio_actual) if precio_actual is not None else ""
                formulario = SedePrecioForm(datos, instance=sede)
                formulario.add_error(
                    None, "El precio cambió. Revisá el importe vigente y confirmá nuevamente."
                )
            elif formulario.cleaned_data["precio_reserva_vigente"] == precio_actual:
                formulario.add_error(
                    "precio_reserva_vigente", "El nuevo importe debe ser diferente del precio actual."
                )
            else:
                sede = formulario.save(commit=False)
                sede.save(update_fields=["precio_reserva_vigente", "actualizado_en"])
                messages.success(request, "El precio por turno fue guardado.")
                return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#precios")

    return render(request, "instalaciones/sede_precio_formulario.html", {
        "sede": sede,
        "formulario": formulario,
        "precio_actual": precio_actual,
        "titulo": "Configurar precio por turno" if precio_actual is None else "Actualizar precio por turno",
        "breadcrumbs": _breadcrumbs_sede(request.user, sede, "precios") + [("Precio por turno", None)],
    })


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_horario_configurar(request, pk, dia=None):
    if not request.user.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    if dia is not None and dia not in SedeHorario.DiaSemana.values:
        raise Http404

    with transaction.atomic():
        sedes = Sede.objects.all()
        if request.method == "POST":
            sedes = sedes.select_for_update()
        sede = get_object_or_404(sedes, pk=pk)
        horarios = {horario.dia_semana: horario for horario in sede.horarios.all()}
        horario = horarios.get(dia)
        inicial = {"dias": [dia] if dia is not None else []}
        if horario is not None:
            inicial.update({
                nombre: getattr(horario, nombre).hour if getattr(horario, nombre) is not None else None
                for nombre in SedeHorarioForm.campos_horarios
            })
            inicial["segunda_franja"] = horario.hora_inicio_2 is not None
        formulario = SedeHorarioForm(
            request.POST if request.method == "POST" else None,
            initial=inicial,
        )

        if request.method == "POST" and formulario.is_valid():
            dias = sorted(set(formulario.cleaned_data["dias"]))
            if formulario.cleaned_data["accion"] == "cerrar":
                sede.horarios.filter(dia_semana__in=dias).delete()
            else:
                for dia_seleccionado in dias:
                    sede.horarios.update_or_create(
                        dia_semana=dia_seleccionado,
                        defaults=formulario.cleaned_data["horas"],
                    )
            sede.save(update_fields=["actualizado_en"])
            messages.success(
                request,
                f'Los horarios de la sede "{sede.nombre}" fueron actualizados '
                f'para {len(dias)} {"día" if len(dias) == 1 else "días"}.',
            )
            return redirect(reverse("instalaciones:sede_detalle", args=[sede.pk]) + "#horarios")

    return render(
        request,
        "instalaciones/sede_horario_formulario.html",
        {
            "sede": sede,
            "formulario": formulario,
            "horarios_semana": [
                {"nombre": nombre, "horario": horarios.get(dia_semana)}
                for dia_semana, nombre in SedeHorario.DiaSemana.choices
            ],
            "breadcrumbs": _breadcrumbs_sede(request.user, sede, "horarios") + [("Horarios", None)],
        },
    )


@login_required
@permission_required("instalaciones.add_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_crear(request):
    formulario = SedeForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and formulario.is_valid():
        try:
            with transaction.atomic():
                sede = formulario.save()
        except IntegrityError as error:
            if (
                not isinstance(error.__cause__, UniqueViolation)
                or error.__cause__.diag.constraint_name != "sede_nombre_unico_sin_mayusculas"
            ):
                raise
            formulario.add_error("nombre", "Ya existe una sede con ese nombre.")
        else:
            messages.success(request, f'La sede "{sede.nombre}" fue creada.')
            return redirect("instalaciones:sede_lista")

    return render(
        request,
        "instalaciones/sede_formulario.html",
        {
            "formulario": formulario,
            "titulo": "Nueva sede",
            "texto_boton": "Crear sede",
            "breadcrumbs": _breadcrumbs_sede(request.user) + [("Nueva sede", None)],
        },
    )


@login_required
@permission_required("instalaciones.change_sede", raise_exception=True)
@require_http_methods(["GET", "POST"])
def sede_editar(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    breadcrumbs = _breadcrumbs_sede(request.user, sede) + [("Editar sede", None)]
    formulario = SedeForm(
        request.POST if request.method == "POST" else None,
        instance=sede,
    )

    if request.method == "POST" and formulario.is_valid():
        sede = formulario.save(commit=False)
        try:
            with transaction.atomic():
                sede.save(update_fields=["nombre", "direccion", "observaciones", "actualizado_en"])
        except IntegrityError as error:
            if (
                not isinstance(error.__cause__, UniqueViolation)
                or error.__cause__.diag.constraint_name != "sede_nombre_unico_sin_mayusculas"
            ):
                raise
            formulario.add_error("nombre", "Ya existe una sede con ese nombre.")
        else:
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
            "breadcrumbs": breadcrumbs,
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
        if nuevo_estado == Sede.Estado.INACTIVA and Evento.objects.filter(
            tipo=Evento.Tipo.RESERVA,
            estado=Evento.Estado.PROGRAMADO,
            turnos__cancha__sede=sede,
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
        try:
            with transaction.atomic():
                cancha = formulario.save()
        except IntegrityError as error:
            if (
                not isinstance(error.__cause__, UniqueViolation)
                or error.__cause__.diag.constraint_name != "cancha_nombre_unico_por_sede_sin_mayusculas"
            ):
                raise
            formulario.add_error("nombre", "Ya existe una cancha con ese nombre en esta sede.")
        else:
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
            "breadcrumbs": _breadcrumbs_sede(request.user, sede, "canchas") + [("Nueva cancha", None)],
        },
    )


@login_required
@permission_required("instalaciones.change_cancha", raise_exception=True)
@require_http_methods(["GET", "POST"])
def cancha_editar(request, sede_pk, pk):
    sede = get_object_or_404(Sede, pk=sede_pk)
    cancha = get_object_or_404(Cancha, pk=pk, sede=sede)
    breadcrumbs = _breadcrumbs_sede(request.user, sede, "canchas") + [
        (cancha.nombre, None),
        ("Editar cancha", None),
    ]
    formulario = CanchaForm(
        request.POST if request.method == "POST" else None,
        sede=sede,
        instance=cancha,
    )

    if request.method == "POST" and formulario.is_valid():
        cancha = formulario.save(commit=False)
        try:
            with transaction.atomic():
                cancha.save(update_fields=["nombre", "superficie", "observaciones", "actualizado_en"])
        except IntegrityError as error:
            if (
                not isinstance(error.__cause__, UniqueViolation)
                or error.__cause__.diag.constraint_name != "cancha_nombre_unico_por_sede_sin_mayusculas"
            ):
                raise
            formulario.add_error("nombre", "Ya existe una cancha con ese nombre en esta sede.")
        else:
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
            "breadcrumbs": breadcrumbs,
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
        if nuevo_estado == Cancha.Estado.INACTIVA and Evento.objects.filter(
            tipo=Evento.Tipo.RESERVA,
            estado=Evento.Estado.PROGRAMADO,
            turnos__cancha=cancha,
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
