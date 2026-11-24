from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import prefetch_related_objects
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from clases.feriados import preparar_feriado, quitar_feriado, registrar_feriado
from clases.forms import FeriadoForm
from clases.models import Feriado
from usuarios.acceso import exigir_acceso_operativo
from usuarios.models import Rol

from .forms import SedeHorarioEspecialForm
from .models import Sede, SedeHorarioEspecial


def _exigir_administracion(usuario):
    usuario = exigir_acceso_operativo(usuario)
    if not (usuario.tiene_rol(Rol.ADMINISTRADOR) and usuario.has_perm("instalaciones.change_sede")):
        raise PermissionDenied
    return usuario


def _parsear_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _parsear_sede_id(valor):
    if valor and str(valor).isdecimal() and len(str(valor)) < 19:
        return int(valor)
    return None


@login_required
@never_cache
@require_GET
def horarios_especiales_lista(request):
    _exigir_administracion(request.user)
    tipo = request.GET.get("tipo", "")
    if tipo not in ("feriado", "particular"):
        tipo = ""
    sede_id = _parsear_sede_id(request.GET.get("sede"))
    sedes = list(Sede.objects.order_by("estado", "nombre", "pk"))
    sedes_validas = {sede.pk for sede in sedes}
    if sede_id not in sedes_validas:
        sede_id = None

    busqueda = request.GET.get("q", "").strip()
    feriados = Feriado.objects.order_by("fecha", "pk")
    especiales = SedeHorarioEspecial.objects.select_related("sede").order_by("fecha", "sede__nombre", "pk")
    if sede_id is not None:
        especiales = especiales.filter(sede_id=sede_id)
    if busqueda:
        feriados = feriados.filter(descripcion__icontains=busqueda)
        especiales = especiales.filter(motivo__icontains=busqueda)

    tipos = (
        ("", "Todos"),
        ("feriado", "Feriados"),
        ("particular", "Horarios especiales"),
    )

    registros = []
    if tipo != "particular":
        for feriado in feriados:
            registros.append({
                "tipo": "feriado",
                "id": feriado.pk,
                "fecha": feriado.fecha,
                "alcance": "Todas las sedes",
                "motivo": feriado.descripcion,
                "cerrada": False,
                "horario": None,
                "orden_tipo": 0,
            })

    if tipo != "feriado":
        for horario in especiales:
            registros.append({
                "tipo": "particular",
                "id": horario.pk,
                "fecha": horario.fecha,
                "alcance": horario.sede.nombre,
                "motivo": horario.motivo,
                "cerrada": horario.cerrada,
                "horario": horario,
                "orden_tipo": 1,
            })

    registros.sort(key=lambda item: (item["fecha"], item["orden_tipo"], item["alcance"].lower(), item["id"]))
    pagina = Paginator(registros, 15).get_page(request.GET.get("pagina"))
    parametros = QueryDict(mutable=True)
    if busqueda:
        parametros["q"] = busqueda
    if tipo:
        parametros["tipo"] = tipo
    if sede_id is not None:
        parametros["sede"] = sede_id
    return render(
        request,
        "instalaciones/horarios_especiales_lista.html",
        {
            "pagina": pagina,
            "sedes": sedes,
            "sede_actual": sede_id,
            "tipo_actual": tipo,
            "tipos": tipos,
            "busqueda": busqueda,
            "parametros": parametros.urlencode(),
        },
    )


def _procesar_horario_especial(request, usuario, *, instance=None, initial=None):
    from .horarios_especiales import guardar_horario_especial, preparar_horario_especial

    es_edicion = instance is not None and instance.pk is not None
    formulario = SedeHorarioEspecialForm(
        request.POST if request.method == "POST" else None,
        instance=instance,
        initial=initial,
    )
    revision = None
    horario_revisado = None

    if request.method == "POST" and formulario.is_valid():
        paso = request.POST.get("paso")
        horario = formulario.cleaned_data["horario"]
        try:
            if paso == "confirmar":
                guardar_horario_especial(
                    usuario,
                    horario,
                    confirmacion=request.POST.get("confirmacion", ""),
                )
                messages.success(
                    request,
                    "El horario especial fue actualizado." if es_edicion else "El horario especial fue creado.",
                )
                return redirect("instalaciones:horarios_especiales")
            if paso == "revisar":
                revision = preparar_horario_especial(usuario, horario)
                if not revision.get("eventos") and not revision.get("conflictos"):
                    guardar_horario_especial(
                        usuario,
                        horario,
                        confirmacion=revision.get("confirmacion"),
                    )
                    messages.success(
                        request,
                        "El horario especial fue actualizado." if es_edicion else "El horario especial fue creado.",
                    )
                    return redirect("instalaciones:horarios_especiales")
                horario_revisado = horario
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)

    return render(
        request,
        "instalaciones/horario_especial_formulario.html",
        {
            "formulario": formulario,
            "es_edicion": es_edicion,
            "horario": instance,
            "revision": revision,
            "horario_revisado": horario_revisado,
        },
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def horario_especial_crear(request):
    usuario = _exigir_administracion(request.user)
    initial = {"fecha": _parsear_fecha(request.GET.get("fecha")) or timezone.localdate()}
    sede_id = _parsear_sede_id(request.GET.get("sede"))
    if sede_id is not None and Sede.objects.filter(pk=sede_id).exists():
        initial["sede"] = sede_id
    return _procesar_horario_especial(request, usuario, initial=initial)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def horario_especial_editar(request, pk):
    usuario = _exigir_administracion(request.user)
    horario = get_object_or_404(SedeHorarioEspecial.objects.select_related("sede"), pk=pk)
    return _procesar_horario_especial(request, usuario, instance=horario)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def horario_especial_quitar(request, pk):
    from .horarios_especiales import guardar_horario_especial, preparar_horario_especial

    usuario = _exigir_administracion(request.user)
    horario = get_object_or_404(SedeHorarioEspecial.objects.select_related("sede"), pk=pk)
    if request.method == "POST":
        try:
            guardar_horario_especial(
                usuario,
                horario,
                confirmacion=request.POST.get("confirmacion", ""),
                quitar=True,
            )
            messages.success(request, "El horario especial fue quitado.")
            return redirect("instalaciones:horarios_especiales")
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)

    try:
        revision = preparar_horario_especial(usuario, horario, quitar=True)
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect("instalaciones:horarios_especiales")

    return render(
        request,
        "instalaciones/horario_especial_quitar.html",
        {
            "horario": horario,
            "revision": revision,
        },
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def feriado_crear(request):
    usuario = _exigir_administracion(request.user)
    fecha_inicial = _parsear_fecha(request.GET.get("fecha")) or timezone.localdate()
    formulario = FeriadoForm(
        request.POST if request.method == "POST" else None,
        initial={"fecha": fecha_inicial},
    )
    revision = None
    clases = []

    if request.method == "POST" and formulario.is_valid():
        paso = request.POST.get("paso")
        try:
            if paso == "confirmar":
                registrar_feriado(
                    usuario,
                    **formulario.cleaned_data,
                    confirmacion=request.POST.get("confirmacion", ""),
                )
                messages.success(request, "El feriado fue registrado.")
                return redirect("instalaciones:horarios_especiales")
            if paso == "revisar":
                revision = preparar_feriado(usuario, **formulario.cleaned_data)
                if not revision["clases"]:
                    registrar_feriado(
                        usuario,
                        **formulario.cleaned_data,
                        confirmacion=revision["confirmacion"],
                    )
                    messages.success(request, "El feriado fue registrado.")
                    return redirect("instalaciones:horarios_especiales")
                prefetch_related_objects(
                    revision["clases"],
                    "evento__turno__cancha__sede",
                    "profesores__profesor",
                    "alumnos__usuario",
                )
                for clase in revision["clases"]:
                    turno = clase.evento.turno
                    clases.append({
                        "id": clase.pk,
                        "sede": turno.cancha.sede.nombre,
                        "cancha": turno.cancha.nombre,
                        "hora": turno.hora_inicio,
                        "hora_fin": turno.hora_fin,
                        "profesores": [v.profesor for v in clase.profesores.all()],
                        "participantes": [v.usuario for v in clase.alumnos.all()],
                    })
            elif paso != "editar":
                raise ValidationError("La acción solicitada no es válida.")
        except ValidationError as error:
            formulario.add_error(None, error)

    return render(
        request,
        "instalaciones/feriado_formulario.html",
        {
            "formulario": formulario,
            "revision": revision,
            "clases": clases,
        },
    )


@login_required
@never_cache
@require_POST
def feriado_quitar(request, pk):
    usuario = _exigir_administracion(request.user)
    try:
        quitar_feriado(usuario, pk)
    except Feriado.DoesNotExist:
        messages.info(request, "El feriado ya no está registrado.")
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, "El feriado fue quitado. Las clases anuladas no se reactivan.")
    return redirect("instalaciones:horarios_especiales")
