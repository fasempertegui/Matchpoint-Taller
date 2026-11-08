from calendar import monthrange

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from usuarios.models import Rol, Usuario

from caja.consultas import contexto_financiero

from .ajustes import contexto_horas_contratacion
from .consultas import listar_contrataciones
from .models import MembresiaUsuario, PlanUsuario
from .contrataciones import (
    ContratacionExistente, contratar_membresia_propia, renovar_plan_propio, revision_precio_contratacion,
)
from .fechas import mes_siguiente, meses_contratables_propios
from .forms import (
    ConfirmacionContratacionPropiaForm, ContratacionMembresiaPropiaForm, RenovacionPlanPropioForm,
)


MODELOS_CONTRATACIONES = {"plan": PlanUsuario, "membresia": MembresiaUsuario}


def _exigir_titular(usuario):
    if not usuario.is_authenticated:
        raise PermissionDenied
    return get_object_or_404(
        Usuario, pk=usuario.pk, is_active=True, debe_cambiar_contrasena=False,
    )


def _contexto(tipo):
    url_lista = reverse("membresias:mis_contrataciones") + f"?tipo={tipo}"
    return {
        "propias": True, "tipo": tipo, "plural": "planes" if tipo == "plan" else "membresías",
        "nombre_tipo": "plan" if tipo == "plan" else "membresía",
        "titulo_lista": "Mis contrataciones", "url_lista": url_lista,
        "ruta_detalle": f"membresias:mi_{tipo}_contratado",
        "ruta_comprobante": f"membresias:mi_{tipo}_comprobante",
        "etiqueta_importe": "Importe aplicado (ARS)",
    }


@login_required
@never_cache
@require_GET
def mis_contrataciones(request):
    titular = _exigir_titular(request.user)
    tipo = request.GET.get("tipo", "plan")
    if tipo not in MODELOS_CONTRATACIONES:
        tipo = "plan"
    if not request.GET.get("tipo") and not PlanUsuario.objects.filter(usuario=titular).exists():
        if MembresiaUsuario.objects.filter(usuario=titular).exists():
            tipo = "membresia"
    modelo = MODELOS_CONTRATACIONES[tipo]
    contrataciones = modelo.objects.filter(usuario=titular).select_related("usuario", tipo)
    datos = listar_contrataciones(contrataciones, request.GET, tipo=tipo, buscar_usuario=False)
    return render(request, "membresias/contratacion_lista.html", {**datos, **_contexto(tipo)})


@login_required
@never_cache
@require_GET
def contratacion_propia_detalle(request, pk, tipo="plan"):
    titular = _exigir_titular(request.user)
    modelo = MODELOS_CONTRATACIONES[tipo]
    contratacion = get_object_or_404(
        modelo.objects.filter(usuario=titular).select_related("usuario", tipo), pk=pk,
    )
    return render(request, "membresias/contratacion_detalle.html", {
        **contexto_financiero(request.user, tipo, contratacion, request.GET),
        **_contexto(tipo), "contratacion": contratacion,
        **(contexto_horas_contratacion(contratacion, request.GET, administrador=False) if tipo == "membresia" else {}),
        "puede_renovar": tipo == "plan" and not _impedimento_renovacion(titular, contratacion)
            and not PlanUsuario.objects.filter(
                usuario=titular, mes_cubierto=mes_siguiente(contratacion.mes_cubierto),
            ).exclude(estado=PlanUsuario.Estado.ANULADO).exists(),
    })


@login_required
@never_cache
@require_GET
def contratacion_propia_comprobante(request, pk, tipo="plan"):
    titular = _exigir_titular(request.user)
    modelo = MODELOS_CONTRATACIONES[tipo]
    contratacion = get_object_or_404(
        modelo.objects.filter(usuario=titular).select_related("usuario", tipo), pk=pk,
    )
    return render(request, "membresias/contratacion_comprobante.html", {
        **_contexto(tipo), "contratacion": contratacion,
    })


def _impedimento_renovacion(titular, referencia):
    if not titular.tiene_rol(Rol.ALUMNO) or titular.tiene_rol(Rol.PROFESOR):
        return "La renovación propia requiere el rol Alumno y no admite Profesor."
    if referencia.estado == PlanUsuario.Estado.ANULADO:
        return "La contratación de referencia está Anulada. Coordiná el caso con administración."
    if referencia.plan.estado != referencia.plan.Estado.ACTIVO:
        return "El plan está Inactivo. Coordiná el caso con administración."
    if mes_siguiente(referencia.mes_cubierto) not in meses_contratables_propios():
        return "El mes de renovación no está habilitado. El mes siguiente al actual se abre desde el día 25 inclusive."
    return ""


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def contratar_membresia(request):
    return _contratacion_propia(request, "membresia")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def renovar_plan(request, pk):
    return _contratacion_propia(request, "plan", referencia_id=pk)


def _contratacion_propia(request, tipo, *, referencia_id=None):
    titular = _exigir_titular(request.user)
    referencia = None
    contexto = {
        **_contexto(tipo), "titulo": "Contratar membresía" if tipo == "membresia" else "Renovar el mismo plan",
        "url_cancelar": reverse("membresias:mis_contrataciones") + f"?tipo={tipo}",
    }
    if tipo == "plan":
        referencia = get_object_or_404(
            PlanUsuario.objects.filter(usuario=titular).select_related("plan"), pk=referencia_id,
        )
        impedimento = _impedimento_renovacion(titular, referencia)
        if impedimento:
            return render(request, "membresias/contratacion_propia_formulario.html", {
                **contexto, "impedimento": impedimento,
            })
        contexto["referencia"] = referencia
        contexto["producto_fijo"] = referencia.plan
        contexto["mes_fijo"] = mes_siguiente(referencia.mes_cubierto)
    paso = request.POST.get("paso", "") if request.method == "POST" else ""
    datos = request.POST if request.method == "POST" else None
    revision = None
    if paso in ("confirmar", "editar"):
        confirmacion = ConfirmacionContratacionPropiaForm(request.POST)
        if confirmacion.is_valid():
            try:
                revision = signing.loads(
                    confirmacion.cleaned_data["revision"], salt="membresias.contratacion_propia", max_age=900,
                )
                if (revision["actor"], revision["tipo"], revision["referencia"]) != (titular.pk, tipo, referencia_id):
                    raise signing.BadSignature
                datos = revision["seleccion"]
            except (signing.BadSignature, KeyError, TypeError):
                revision = None
        if revision is None:
            messages.error(request, "La revisión venció o no es válida. Revisá la selección antes de confirmar.")
            datos = None
    clase_formulario = ContratacionMembresiaPropiaForm if tipo == "membresia" else RenovacionPlanPropioForm
    iniciales = {"membresia": request.GET.get("membresia"), "mes_cubierto": timezone.localdate().replace(day=1)}
    formulario = clase_formulario(datos, initial=iniciales)
    contexto["formulario"] = formulario
    if tipo == "membresia" and not formulario.fields["membresia"].queryset.exists():
        return render(request, "membresias/contratacion_propia_formulario.html", {
            **contexto, "formulario": None, "impedimento": "No hay membresías Activas disponibles para contratar.",
        })
    if paso in ("revisar", "confirmar") and formulario.is_bound and formulario.is_valid():
        producto = formulario.cleaned_data["membresia"] if tipo == "membresia" else referencia.plan
        mes = formulario.cleaned_data["mes_cubierto"] if tipo == "membresia" else contexto["mes_fijo"]
        observaciones = formulario.cleaned_data["observaciones"]
        if paso == "confirmar" and revision is not None:
            servicio = contratar_membresia_propia if tipo == "membresia" else renovar_plan_propio
            argumentos = {"membresia_id": producto.pk} if tipo == "membresia" else {"referencia_id": referencia_id}
            try:
                contrato = servicio(
                    titular, **argumentos, mes_cubierto=mes, revision_precio=revision["precio"],
                    observaciones=observaciones,
                )
            except ContratacionExistente as error:
                formulario.add_error(None, error)
                contexto["contratacion_existente"] = error.contratacion
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "La contratación fue registrada. El cobro se gestiona por separado.")
                return redirect(contexto["ruta_detalle"], pk=contrato.pk)
        elif paso == "revisar":
            seleccion = {"observaciones": observaciones}
            if tipo == "membresia":
                seleccion.update({"membresia": producto.pk, "mes_cubierto": mes.isoformat()})
            token = signing.dumps({
                "actor": titular.pk, "tipo": tipo, "referencia": referencia_id, "seleccion": seleccion,
                "precio": revision_precio_contratacion(
                    titular, titular, producto, mes_cubierto=mes, referencia=referencia,
                ),
            }, salt="membresias.contratacion_propia", compress=True)
            confirmacion = ConfirmacionContratacionPropiaForm(initial={"revision": token})
            contexto.update({
                "formulario": confirmacion, "producto": producto, "mes": mes,
                "fecha_fin": mes.replace(day=monthrange(mes.year, mes.month)[1]),
                "observaciones": observaciones,
                "confirmacion": confirmacion,
            })
    return render(request, "membresias/contratacion_propia_formulario.html", contexto)
