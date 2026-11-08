from calendar import monthrange
from datetime import date, datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from membresias.fechas import mes_siguiente
from membresias.models import MembresiaUsuario
from usuarios.models import Rol, Usuario

from .comercial import (
    _leer, actualizar_socios, coberturas, confirmar_reserva, gestionar_invitados,
    inicio_reserva, preparar_reserva, registrar_resultado, responder_invitacion, version_resultado,
)
from .forms import InvitadosReservaForm, OrganizadorReservaForm, ResultadoReservaForm, TurnoReservaForm, UsoMembresiaForm
from .horas import horas_disponibles_organizador, resumen_horas_del_mes
from .models import Evento, Reserva, ReservaInvitado
from .servicios import exigir_acceso_reservas
from .views import _obtener_reserva_para_consulta


@login_required
@never_cache
@require_GET
def buscar_invitados(request):
    exigir_acceso_reservas(request.user)
    busqueda = request.GET.get("q", "").strip()[:100]
    if len(busqueda) < 2:
        return JsonResponse({"resultados": [], "hay_mas": False})
    reserva = None
    if "reserva" in request.GET:
        identificador = request.GET.get("reserva", "")
        reserva, administrador = _obtener_reserva_para_consulta(
            request.user, identificador if identificador.isdecimal() else None,
        )
        if not administrador and reserva.organizador_id != request.user.pk:
            raise PermissionDenied
        if reserva.evento.estado != Evento.Estado.PROGRAMADO or timezone.now() >= inicio_reserva(reserva):
            raise PermissionDenied
    organizador_id = request.GET.get("organizador", "")
    formulario = InvitadosReservaForm(
        organizador_id=reserva.organizador_id if reserva else organizador_id if organizador_id.isdecimal() else request.user.pk,
        reserva=reserva,
    )
    personas = formulario.fields["invitados"].queryset
    for termino in busqueda.split():
        personas = personas.filter(Q(first_name__icontains=termino) | Q(last_name__icontains=termino) | Q(username__icontains=termino))
    excluidos = [valor for valor in request.GET.getlist("excluir") if valor.isdecimal()]
    filas = list(personas.exclude(pk__in=excluidos)[:11])
    return JsonResponse({
        "resultados": [{"id": persona.pk, "nombre": str(persona), "usuario": persona.username} for persona in filas[:10]],
        "hay_mas": len(filas) > 10,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def crear_reserva(request):
    administrador = exigir_acceso_reservas(request.user)
    turno_form = TurnoReservaForm(request.GET)
    contexto = {"titulo": "Nueva reserva", "turno_form": turno_form, "administrador": administrador}
    contexto["url_cancelar"] = reverse("agenda:agenda")
    if not turno_form.is_valid():
        return render(request, "reservas/reserva_crear.html", contexto)
    turno = turno_form.cleaned_data
    total_pasos = 4 if administrador else 3
    contexto.update({"total_pasos": total_pasos, "pasos": range(1, total_pasos + 1), "numero_paso": 1, "nombre_paso": "Organizador"})
    contexto["turno"] = turno
    contexto["hora"] = time(turno["hora"])
    paso = request.POST.get("paso", "")
    datos = request.POST if request.method == "POST" else None
    revisada = None
    if paso in ("confirmar", "editar"):
        try:
            revisada = _leer(request.user, request.POST.get("confirmacion"), "crear")["datos"]
            if any(str(revisada[campo]) != str(valor) for campo, valor in {"cancha": turno["cancha"].pk, "fecha": turno["fecha"].isoformat(), "hora": turno["hora"]}.items()):
                raise ValidationError("El turno cambió. Revisá nuevamente.")
            datos = revisada
        except ValidationError as error:
            messages.error(request, error.messages[0])
            datos, paso = None, ""
    contexto["invitados_borrador"] = (datos.getlist("invitados") if hasattr(datos, "getlist") else datos.get("invitados", [])) if datos else []
    contexto["observaciones_borrador"] = datos.get("observaciones", "") if datos else ""
    organizador_form = OrganizadorReservaForm(
        datos, fecha=turno["fecha"], hora=contexto["hora"],
    ) if administrador else None
    organizador = request.user if not administrador else None
    if administrador:
        contexto["organizador_form"] = organizador_form
        valor_organizador = organizador_form["organizador"].value()
        if valor_organizador and str(valor_organizador).isdecimal():
            contexto["usuario_seleccionado"] = organizador_form.fields["organizador"].queryset.filter(pk=valor_organizador).first()
        if organizador_form.is_bound and organizador_form.is_valid():
            organizador = organizador_form.cleaned_data["organizador"]
            if paso == "volver_organizador":
                contexto["usuario_seleccionado"] = organizador
                contexto["url_buscar_usuarios"] = reverse("agenda:buscar_organizadores")
                return render(request, "reservas/reserva_crear.html", contexto)
        else:
            contexto["url_buscar_usuarios"] = reverse("agenda:buscar_organizadores")
            return render(request, "reservas/reserva_crear.html", contexto)
    contexto.update({"numero_paso": total_pasos - 2, "nombre_paso": "Modalidad"})
    contexto["organizador"] = organizador
    contrato = coberturas({organizador.pk}, turno["fecha"]).get(organizador.pk)
    horas_disponibles = horas_disponibles_organizador(contrato) if contrato else 0
    puede_membresia = horas_disponibles > 0
    contexto["horas_disponibles"] = horas_disponibles
    contexto["puede_membresia"] = puede_membresia
    contexto["contrato_disponible"] = contrato
    contexto["puede_normal"] = turno["cancha"].sede.precio_reserva_vigente is not None and turno["cancha"].sede.precio_reserva_vigente > 0
    modalidad = datos.get("modalidad") if datos and paso != "organizador" else None
    if modalidad not in ("normal", "membresia"):
        return render(request, "reservas/reserva_crear.html", contexto)
    contexto.update({"numero_paso": total_pasos - 1, "nombre_paso": "Invitados"})
    contexto["modalidad"] = modalidad
    formulario = InvitadosReservaForm(
        datos if paso in ("revisar", "confirmar", "editar") else None, organizador_id=organizador.pk,
        initial={"invitados": contexto["invitados_borrador"], "observaciones": contexto["observaciones_borrador"]},
    )
    contexto["formulario"] = formulario
    valores = formulario["invitados"].value() or []
    identificadores = [valor for valor in valores if str(valor).isdecimal()]
    contexto["invitados_seleccionados"] = formulario.fields["invitados"].queryset.filter(pk__in=identificadores)
    contexto["url_buscar_invitados"] = reverse("reservas:buscar_invitados") + f"?organizador={organizador.pk}"
    if paso in ("revisar", "confirmar") and formulario.is_valid():
        seleccion = {
            "organizador": organizador.pk, "cancha": turno["cancha"].pk, "fecha": turno["fecha"].isoformat(),
            "hora": turno["hora"], "modalidad": modalidad,
            "invitados": [u.pk for u in formulario.cleaned_data["invitados"]], "observaciones": formulario.cleaned_data["observaciones"],
        }
        try:
            if paso == "confirmar" and revisada is not None:
                reserva = confirmar_reserva(request.user, request.POST.get("confirmacion"), coordenadas={"cancha": turno["cancha"].pk, "fecha": turno["fecha"].isoformat(), "hora": turno["hora"]})
                messages.success(request, f"La reserva {reserva.numero} fue registrada. El cobro se registra por separado.")
                return redirect("reservas:reserva_detalle", pk=reserva.pk)
            contexto["revision"] = preparar_reserva(request.user, seleccion)
            contexto.update({"numero_paso": total_pasos, "nombre_paso": "Revisión"})
        except ValidationError as error:
            formulario.add_error(None, error)
    return render(request, "reservas/reserva_crear.html", contexto)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def reserva_invitados(request, pk):
    reserva, administrador = _obtener_reserva_para_consulta(request.user, pk)
    if not administrador and reserva.organizador_id != request.user.pk:
        raise PermissionDenied
    if reserva.evento.estado != Evento.Estado.PROGRAMADO or timezone.now() >= inicio_reserva(reserva):
        messages.error(request, "Sólo se gestionan invitados antes del inicio de una reserva Programada.")
        return redirect("reservas:reserva_detalle", pk=pk)
    datos = request.POST if request.method == "POST" else None
    seleccion = list(reserva.invitados.filter(estado="vigente").exclude(respuesta="negativa").values_list("usuario_id", flat=True))
    formulario = InvitadosReservaForm(datos, organizador_id=reserva.organizador_id, reserva=reserva, initial={"invitados": seleccion})
    contexto = {"reserva": reserva, "formulario": formulario, "titulo": "Gestionar invitados"}
    contexto["advertencias_invitados"] = [
        "Retirar o reincorporar a una persona conserva su respuesta e historia"
        + ("; agregar invitados es opcional y no modifica el precio del turno" if not reserva.es_con_membresia else ""),
        "Las invitaciones rechazadas no se vuelven a enviar",
    ]
    valores = formulario["invitados"].value() or []
    contexto["invitados_seleccionados"] = formulario.fields["invitados"].queryset.filter(
        pk__in=[valor for valor in valores if str(valor).isdecimal()],
    )
    contexto["url_buscar_invitados"] = reverse("reservas:buscar_invitados") + f"?reserva={reserva.pk}"
    if request.POST.get("paso") in ("revisar", "confirmar") and formulario.is_valid():
        try:
            ids = {u.pk for u in formulario.cleaned_data["invitados"]}
            if request.POST.get("paso") == "confirmar":
                gestionar_invitados(request.user, pk, ids, confirmacion=request.POST.get("confirmacion") or "")
                messages.success(request, "Los invitados fueron actualizados.")
                return redirect("reservas:reserva_detalle", pk=pk)
            contexto["revision"] = gestionar_invitados(request.user, pk, ids)
        except ValidationError as error:
            formulario.add_error(None, error)
    return render(request, "reservas/reserva_invitados.html", contexto)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def reserva_socios(request, pk):
    reserva, administrador = _obtener_reserva_para_consulta(request.user, pk)
    if not administrador and reserva.organizador_id != request.user.pk:
        raise PermissionDenied
    contexto = {"reserva": reserva, "titulo": "Actualizar socios"}
    try:
        if request.method == "POST":
            actualizar_socios(request.user, pk, confirmacion=request.POST.get("confirmacion") or "")
            messages.success(request, "La condición de socios fue actualizada.")
            return redirect("reservas:reserva_detalle", pk=pk)
        contexto["revision"] = actualizar_socios(request.user, pk)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("reservas:reserva_detalle", pk=pk)
    return render(request, "reservas/reserva_gestion.html", contexto)


@login_required
@never_cache
@require_POST
def reserva_responder(request, pk):
    try:
        responder_invitacion(request.user, pk, request.POST.get("respuesta"))
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, "Tu respuesta fue registrada.")
    return redirect("reservas:reserva_detalle", pk=pk)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def reserva_resultado(request, pk):
    reserva, administrador = _obtener_reserva_para_consulta(request.user, pk)
    if not administrador:
        raise PermissionDenied
    if not reserva.es_con_membresia or reserva.evento.estado != Evento.Estado.FINALIZADO or reserva.resultado_corregido_en:
        messages.error(request, "La reserva no admite registro o corrección de resultado.")
        return redirect("reservas:reserva_detalle", pk=pk)
    formulario = ResultadoReservaForm(request.POST if request.method == "POST" else None, reserva=reserva, initial={"version": version_resultado(request.user, reserva)})
    if request.method == "POST" and formulario.is_valid():
        try:
            registrar_resultado(request.user, pk, formulario.cleaned_data["resultado"], formulario.cleaned_data.get("motivo", ""), version=formulario.cleaned_data["version"])
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "El resultado fue registrado sin modificar horas ni cobros.")
            return redirect("reservas:reserva_detalle", pk=pk)
    return render(request, "reservas/reserva_gestion.html", {"reserva": reserva, "titulo": "Resultado de uso", "formulario": formulario, "resultado": True})


@login_required
@never_cache
@require_GET
def mis_reservas(request):
    exigir_acceso_reservas(request.user)
    consulta = Reserva.objects.filter(Q(organizador=request.user) | Q(invitados__usuario=request.user)).distinct().select_related("evento__turno__cancha__sede").order_by("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
    return render(request, "reservas/mis_reservas.html", {"pagina": Paginator(consulta, 25).get_page(request.GET.get("pagina"))})


@login_required
@never_cache
@require_GET
def uso_membresia(request):
    usuario = get_object_or_404(Usuario, pk=request.user.pk, is_active=True, debe_cambiar_contrasena=False)
    administrador = usuario.tiene_rol(Rol.ADMINISTRADOR)
    hoy = timezone.localdate()
    parametros = request.GET.copy()
    parametros.setdefault("modo", "rango" if request.GET.get("desde") or request.GET.get("hasta") else "mes")
    parametros.setdefault("mes", hoy.strftime("%Y-%m"))
    parametros.setdefault("desde", hoy.replace(day=1).isoformat())
    parametros.setdefault("hasta", hoy.replace(day=monthrange(hoy.year, hoy.month)[1]).isoformat())
    if administrador:
        parametros.setdefault("usuario", str(request.user.pk))
    formulario = UsoMembresiaForm(parametros, administrador=administrador)
    contexto = {"formulario": formulario}
    if formulario.is_valid():
        titular = formulario.cleaned_data["usuario"] if administrador else request.user
        desde, hasta = formulario.cleaned_data["desde"], formulario.cleaned_data["hasta"]
        meses = []
        mes = desde.replace(day=1)
        while mes <= hasta:
            contrato = MembresiaUsuario.objects.filter(usuario=titular, mes_cubierto=mes).exclude(
                estado=MembresiaUsuario.Estado.ANULADO,
            ).first()
            meses.extend(resumen_horas_del_mes(titular.pk, mes, contrato))
            mes = mes_siguiente(mes)
        reservas = Reserva.objects.filter(organizador=titular, membresia_usuario__isnull=False, evento__turno__fecha__range=(desde, hasta)).select_related("evento__turno__cancha__sede").order_by("evento__turno__fecha", "evento__turno__hora_inicio")
        invitaciones = ReservaInvitado.objects.filter(usuario=titular, reserva__evento__turno__fecha__range=(desde, hasta)).select_related("reserva__evento__turno__cancha__sede")
        participaciones = [{"invitacion": i, "respuesta_texto": i.respuesta_visible(inicio_reserva(i.reserva))} for i in invitaciones]
        contexto.update({"titular": titular, "meses": meses, "reservas": reservas, "invitaciones": participaciones})
    return render(request, "reservas/uso_membresia.html", contexto)
