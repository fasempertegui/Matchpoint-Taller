from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .finanzas import CAMPOS_DEVOLUCION, leer_revision_devolucion, revision_devolucion, situacion_financiera
from .forms import DevolucionForm, SeleccionOrigenMovimientoForm
from .ingresos import ORIGENES, filtrar_origenes
from .models import SesionCaja
from .movimientos import registrar_movimiento
from .servicios import efectivo_esperado, exigir_acceso_caja


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def devolucion_crear(request, pk):
    actor = exigir_acceso_caja(request.user)
    sesion = get_object_or_404(SesionCaja, pk=pk)
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    if sesion.estado != "abierta" and request.method == "GET":
        messages.error(request, "La sesión está cerrada y no admite devoluciones nuevas.")
        return redirect("caja:sesion_detalle", pk=pk)
    datos = request.POST if request.method == "POST" else request.GET
    paso = request.POST.get("paso")
    if sesion.estado != "abierta" and paso != "confirmar":
        messages.error(request, "La sesión está cerrada y no admite devoluciones nuevas.")
        return redirect("caja:sesion_detalle", pk=pk)
    tipo = datos.get("tipo") or request.GET.get("tipo")
    if paso in ("editar", "confirmar"):
        try:
            firmado = leer_revision_devolucion(actor, pk, request.POST.get("confirmacion"))
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("caja:devolucion_crear", pk=pk)
        tipo = firmado["tipo"]
        datos = {**firmado["datos"], "origen": firmado["origen"]}
    tipo_previo = tipo
    if paso == "volver_tipo":
        tipo = None
    borrador = {campo: datos[campo] for campo in CAMPOS_DEVOLUCION if campo in datos}
    contexto = {
        "devolucion": True, "titulo": "Registrar devolución", "sesion": sesion,
        "tipo": tipo, "tipo_previo": tipo_previo, "borrador": borrador,
        "total_pasos": 3 if tipo == "general" else 4,
        "pasos": range(1, 4 if tipo == "general" else 5), "numero_paso": 1, "nombre_paso": "Origen de la devolución",
        "opciones_origen": [
            ("reserva", "Reserva", "Devolvé dinero de una reserva concreta"),
            ("plan", "Contratación de plan", "Devolvé dinero de una contratación de plan"),
            ("membresia", "Contratación de membresía", "Devolvé dinero de una contratación de membresía"),
            ("general", "Devolución sin vínculo", "Registrá el reintegro con un concepto que explique el motivo"),
        ],
    }
    if tipo is None:
        return render(request, "caja/ingreso_origen.html", contexto)
    if tipo != "general" and tipo not in ORIGENES:
        raise Http404
    contexto["tipo_texto"] = dict((valor, nombre) for valor, nombre, _ in contexto["opciones_origen"])[tipo]
    origen = None
    situacion = None
    if tipo != "general":
        seleccion = SeleccionOrigenMovimientoForm(datos if datos.get("origen") else None, tipo=tipo, devolucion=True)
        contexto.update({"seleccion": seleccion, "numero_paso": 2, "nombre_paso": "Seleccionar registro"})
        if paso in ("volver", "buscar") or "pagina_origen" in datos or not datos.get("origen") or not seleccion.is_valid():
            busqueda = datos.get("q", "").strip()[:100]
            consulta = filtrar_origenes(seleccion.fields["origen"].queryset, tipo, busqueda)
            contexto.update({"busqueda": busqueda, "registros": Paginator(consulta.order_by("-pk"), 8).get_page(datos.get("pagina_origen")),
                             "origen_seleccionado": str(datos.get("origen", ""))})
            return render(request, "caja/ingreso_origen.html", contexto)
        origen = seleccion.cleaned_data["origen"]
        situacion = situacion_financiera(tipo, origen.pk)
        contexto.update({"origen": origen, "situacion": situacion, "categoria_texto": "Devoluciones",
                         "importe_aplicado": origen.total if tipo == "reserva" else origen.precio_aplicado})
    contexto.update({"numero_paso": contexto["total_pasos"] - 1, "nombre_paso": "Datos de la devolución"})
    formulario = DevolucionForm(datos if paso in ("revisar", "confirmar", "editar") else None, initial=borrador)
    contexto["formulario"] = formulario
    if situacion:
        formulario.fields["monto"].widget.attrs["max"] = format(situacion["maximo_devolucion"], ".2f")
    if paso in ("revisar", "confirmar") and formulario.is_valid():
        campos = formulario.cleaned_data
        if paso == "confirmar":
            try:
                movimiento = registrar_movimiento(actor, pk, clase="egreso", categoria_egreso="devoluciones", tipo_origen=tipo,
                                                  origen_id=origen.pk if origen else None, revision_devolucion=request.POST.get("confirmacion"), **campos)
            except ValidationError as error:
                sesion.refresh_from_db(fields=["estado"])
                if sesion.estado != "abierta":
                    messages.error(request, error.messages[0])
                    return redirect("caja:sesion_detalle", pk=pk)
                formulario.add_error(None, error.messages)
                if origen:
                    situacion = situacion_financiera(tipo, origen.pk)
                    contexto["situacion"] = situacion
                    formulario.fields["monto"].widget.attrs["max"] = format(situacion["maximo_devolucion"], ".2f")
            else:
                messages.success(request, f"La devolución {movimiento.numero} fue registrada.")
                return redirect("caja:movimiento_detalle", pk=movimiento.pk)
        elif situacion is not None and campos["monto"] > situacion["maximo_devolucion"]:
            formulario.add_error("monto", f"El máximo disponible es ARS {situacion['maximo_devolucion']:.2f}.")
        elif campos["medio_pago"] == "efectivo" and campos["monto"] > efectivo_esperado(sesion):
            formulario.add_error("monto", "El efectivo disponible no alcanza para esta devolución.")
        else:
            contexto.update({"numero_paso": contexto["total_pasos"], "nombre_paso": "Revisar devolución", "revision": campos,
                             "medio_texto": dict(formulario.fields["medio_pago"].choices)[campos["medio_pago"]],
                             "confirmacion": revision_devolucion(actor, pk, tipo, origen.pk if origen else None, campos, situacion)})
    return render(request, "caja/devolucion_formulario.html", contexto)
