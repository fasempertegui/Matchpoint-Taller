from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from clases.models import Clase
from membresias.continuidad import contexto_continuidad
from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.models import Evento, Reserva
from reservas.servicios import invitaciones_por_responder
from usuarios.models import Rol


def contexto_inicio_portal(usuario):
    ahora = timezone.localtime()
    mes = ahora.date().replace(day=1)
    contexto = {"hoy": ahora.date(), "clases_proximas": [], "reservas_proximas": [], "contrataciones_mes": [], "pendientes": []}
    if not usuario.esta_habilitado or usuario.debe_cambiar_contrasena:
        return contexto
    futuras = Q(evento__turno__fecha__gt=ahora.date()) | Q(
        evento__turno__fecha=ahora.date(), evento__turno__hora_inicio__gt=ahora.time(),
    )
    clases = list(Clase.objects.filter(
        Q(profesores__profesor=usuario) | Q(alumnos__usuario=usuario), futuras,
        evento__estado=Evento.Estado.PROGRAMADO,
    ).select_related("evento__turno__cancha__sede").distinct().order_by(
        "evento__turno__fecha", "evento__turno__hora_inicio", "pk",
    )[:4])
    contexto["mostrar_clases"] = bool(clases) or usuario.tiene_rol(Rol.PROFESOR) or usuario.tiene_rol(Rol.ALUMNO)
    if clases:
        contexto["proxima_clase"] = clases[0]
        contexto["clases_proximas"] = clases[1:]
    if usuario.puede_reservar:
        contexto["reservas_proximas"] = list(Reserva.objects.filter(
            Q(organizador=usuario) | Q(invitados__usuario=usuario, invitados__respuesta="afirmativa"),
            futuras, evento__estado=Evento.Estado.PROGRAMADO,
        ).select_related("evento__turno__cancha__sede").distinct().order_by(
            "evento__turno__fecha", "evento__turno__hora_inicio", "pk",
        )[:3])
        invitaciones = invitaciones_por_responder(usuario, ahora).count()
        if invitaciones:
            contexto["pendientes"].append({
                "texto": f"Invitaciones por responder: {invitaciones}",
                "url": reverse("reservas:mis_invitaciones", query={"vista": "por_responder"}),
                "accion": "Ver invitaciones",
            })
    for tipo, modelo in (("plan", PlanUsuario), ("membresia", MembresiaUsuario)):
        contratos = modelo.objects.filter(
            usuario=usuario, mes_cubierto__in=(mes, (mes - timedelta(days=1)).replace(day=1)),
        ).exclude(estado=modelo.Estado.ANULADO).select_related(tipo).order_by("-mes_cubierto", "pk")
        for contrato in contratos:
            if contrato.mes_cubierto == mes and contrato.estado == modelo.Estado.ACTIVO:
                contexto["contrataciones_mes"].append({
                    "nombre": contrato.producto.nombre, "tipo": "Plan" if tipo == "plan" else "Membresía",
                    "url": reverse(f"membresias:mi_{tipo}_contratado", args=[contrato.pk]),
                })
            continuidad = contexto_continuidad(contrato, usuario, tipo=tipo)["continuidad"]
            if continuidad["puede_responder"] and not contrato.respuesta_continuidad:
                contexto["pendientes"].append({
                    "texto": f"Continuidad de {contrato.producto.nombre}",
                    "url": f"{continuidad['url_responder']}?{urlencode({'siguiente': reverse('inicio')})}",
                    "accion": "Responder encuesta",
                    "modal": True,
                })
    return contexto
