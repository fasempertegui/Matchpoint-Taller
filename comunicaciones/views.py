from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from auditoria.contexto import contexto_auditoria
from usuarios.acceso import exigir_acceso_operativo
from usuarios.models import Rol, Usuario

from .forms import ConfiguracionNotificacionesForm
from .models import ConfiguracionNotificaciones, EnvioEmail, Notificacion


@login_required
@never_cache
@require_GET
def envios_lista(request):
    if not Usuario.objects.filter(
        pk=request.user.pk, is_active=True, correo_verificado_en__isnull=False, debe_cambiar_contrasena=False,
        roles__rol__codigo=Rol.ADMINISTRADOR,
    ).exists():
        raise PermissionDenied
    registros = EnvioEmail.objects.defer("datos", "reserva_token", "clave")
    estado = request.GET.get("estado", "")
    tipo = request.GET.get("tipo", "")
    busqueda = request.GET.get("q", "").strip()[:150]
    if estado in EnvioEmail.Estado.values:
        registros = registros.filter(estado=estado)
    else:
        estado = ""
    if tipo in EnvioEmail.Tipo.values:
        registros = registros.filter(tipo=tipo)
    else:
        tipo = ""
    if busqueda:
        registros = registros.filter(destinatario__icontains=busqueda)
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "comunicaciones/envios_lista.html", {
        "pagina": Paginator(registros, 25).get_page(request.GET.get("pagina")),
        "estados": EnvioEmail.Estado.choices, "tipos": EnvioEmail.Tipo.choices,
        "estado_actual": estado, "tipo_actual": tipo, "busqueda": busqueda,
        "filtros": filtros.urlencode(),
    })


CATEGORIAS_NOTIFICACION = {
    EnvioEmail.Tipo.RESERVA_CREADA: ("reserva", "reserva"),
    EnvioEmail.Tipo.INVITACION: ("reserva", "reserva"),
    EnvioEmail.Tipo.RESPUESTA_INVITACION: ("reserva", "reserva"),
    EnvioEmail.Tipo.RECORDATORIO_RESERVA: ("reserva", "reserva"),
    EnvioEmail.Tipo.RETIRADA_INVITACION: ("reserva", "alerta"),
    EnvioEmail.Tipo.RESERVA_ANULADA: ("reserva", "alerta"),
    EnvioEmail.Tipo.ASIGNACION_CLASE: ("clase", "clase"),
    EnvioEmail.Tipo.GENERACION_CLASES: ("clase", "clase"),
    EnvioEmail.Tipo.CANCHA_CAMBIADA: ("clase", "clase"),
    EnvioEmail.Tipo.RECORDATORIO_CLASE: ("clase", "clase"),
    EnvioEmail.Tipo.NO_ASISTO: ("clase", "advertencia"),
    EnvioEmail.Tipo.RETIRADA_CLASE: ("clase", "alerta"),
    EnvioEmail.Tipo.CLASE_ANULADA: ("clase", "alerta"),
    EnvioEmail.Tipo.CONTRATACION: ("finanzas", "positivo"),
    EnvioEmail.Tipo.MOVIMIENTO: ("finanzas", "positivo"),
    EnvioEmail.Tipo.AJUSTE_HORAS: ("finanzas", "cuenta"),
    EnvioEmail.Tipo.AJUSTE_IMPORTE: ("finanzas", "cuenta"),
    EnvioEmail.Tipo.CONTINUIDAD: ("finanzas", "cuenta"),
    EnvioEmail.Tipo.CONTRATACION_ANULADA: ("finanzas", "alerta"),
}


@login_required
@never_cache
@require_GET
def notificaciones_lista(request):
    usuario = exigir_acceso_operativo(request.user)
    registros = Notificacion.objects.filter(destinatario=usuario)
    estado = request.GET.get("estado", "")
    if estado in ("pendientes", "leidas"):
        registros = registros.filter(leida=estado == "leidas")
    else:
        estado = ""
    pagina = Paginator(registros, 25).get_page(request.GET.get("pagina"))
    for notificacion in pagina:
        notificacion.icono_categoria, notificacion.tono_categoria = CATEGORIAS_NOTIFICACION.get(
            notificacion.tipo, ("cuenta", "cuenta"),
        )
    return render(request, "comunicaciones/notificaciones_lista.html", {
        "pagina": pagina,
        "estado_actual": estado, "filtros": f"estado={estado}" if estado else "",
    })


@login_required
@never_cache
@require_POST
def notificacion_leer(request, pk):
    usuario = exigir_acceso_operativo(request.user)
    notificacion = get_object_or_404(Notificacion, pk=pk, destinatario=usuario)
    actualizadas = Notificacion.objects.filter(pk=notificacion.pk, destinatario=usuario, leida=False).update(
        leida=True, fecha_lectura=timezone.now(),
    )
    if notificacion.ruta:
        return redirect(notificacion.ruta)
    if actualizadas:
        messages.success(request, "Notificación marcada como leída.")
    else:
        messages.info(request, "La notificación ya estaba marcada como leída.")
    return redirect("comunicaciones:notificaciones_lista")


@login_required
@never_cache
@require_POST
def notificaciones_leer_todas(request):
    usuario = exigir_acceso_operativo(request.user)
    actualizadas = Notificacion.objects.filter(destinatario=usuario, leida=False).update(
        leida=True, fecha_lectura=timezone.now(),
    )
    if actualizadas == 1:
        messages.success(request, "Se marcó 1 notificación como leída.")
    elif actualizadas > 1:
        messages.success(request, f"Se marcaron {actualizadas} notificaciones como leídas.")
    else:
        messages.info(request, "No había notificaciones pendientes de lectura.")
    return redirect("comunicaciones:notificaciones_lista")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def configuracion_notificaciones(request):
    actor = exigir_acceso_operativo(request.user, bloquear=request.method == "POST")
    if not actor.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    consulta = ConfiguracionNotificaciones.objects
    if request.method == "POST":
        consulta = consulta.select_for_update()
    configuracion = consulta.get(pk=1)
    campo = request.POST.get("regla", "") if request.method == "POST" else request.GET.get("editar", "")
    if (campo or request.method == "POST") and campo not in ConfiguracionNotificacionesForm.Meta.fields:
        raise Http404
    valores = (
        ("anticipacion_clases_minutos", f"{configuracion.anticipacion_clases_minutos} minutos antes del inicio"),
        ("anticipacion_reservas_minutos", f"{configuracion.anticipacion_reservas_minutos} minutos antes del inicio"),
        ("dia_apertura_continuidad", f"Día {configuracion.dia_apertura_continuidad} del mes cubierto"),
        ("dia_recordatorio_continuidad", f"Día {configuracion.dia_recordatorio_continuidad} del mes cubierto"
            if configuracion.dia_recordatorio_continuidad else "Último día del mes cubierto"),
        ("dia_cierre_continuidad", f"Día {configuracion.dia_cierre_continuidad} del mes siguiente, inclusive"),
        ("hora_continuidad", f"{configuracion.hora_continuidad:%H:%M} (Salta)"),
    )
    reglas = [{"campo": nombre, "titulo": configuracion._meta.get_field(nombre).verbose_name, "valor": valor}
              for nombre, valor in valores]
    formulario = None
    if campo:
        formulario = ConfiguracionNotificacionesForm(
            request.POST if request.method == "POST" else None, instance=configuracion, campo=campo,
        )
        if request.method == "POST" and formulario.is_valid():
            if formulario.has_changed():
                with contexto_auditoria(actor):
                    formulario.save(commit=False).save(update_fields=(campo, "actualizado_en"))
            messages.success(request, "Se guardó la regla de notificación.")
            return redirect("comunicaciones:configuracion_notificaciones")
    return render(request, "comunicaciones/configuracion.html", {
        "configuracion": configuracion, "formulario": formulario, "reglas": reglas, "regla_actual": campo,
    })
