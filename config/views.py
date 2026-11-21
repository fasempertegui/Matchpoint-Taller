from datetime import timedelta

from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from membresias.continuidad import ventana_continuidad
from membresias.models import MembresiaUsuario, PlanUsuario
from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .inicio_portal import contexto_inicio_portal


@require_GET
def landing(request):
    usuario = request.user
    if usuario.is_authenticated:
        puede_ver_oferta = (
            usuario.is_active
            and not usuario.debe_cambiar_contrasena
            and usuario.roles.filter(rol__codigo__in=(Rol.PUBLICO, Rol.ADMINISTRADOR)).exists()
        )
        url_planes = reverse("oferta:planes") if puede_ver_oferta else reverse("inicio")
        url_membresias = reverse("oferta:membresias") if puede_ver_oferta else reverse("inicio")
        if usuario.esta_habilitado:
            url_reservas = reverse("agenda:agenda")
        elif usuario.correo_verificado_en is None:
            url_reservas = reverse("estado_verificacion")
        else:
            url_reservas = reverse("inicio")
    else:
        url_login = reverse("login")
        url_planes = f"{url_login}?next={reverse('oferta:planes')}"
        url_reservas = f"{url_login}?next={reverse('agenda:agenda')}"
        url_membresias = f"{url_login}?next={reverse('oferta:membresias')}"

    modalidades = [
        {
            "titulo": "Clases",
            "descripcion": "Entrená en grupo o de forma individual con un plan mensual.",
            "enlace": "Ver planes",
            "url": url_planes,
        },
        {
            "titulo": "Reservas",
            "descripcion": "Elegí sede y reservá un turno para jugar.",
            "enlace": "Ver reservas",
            "url": url_reservas,
        },
        {
            "titulo": "Membresías",
            "descripcion": "Hacete socio y usá tus horas para organizar partidos o jugar como invitado.",
            "enlace": "Ver membresías",
            "url": url_membresias,
        },
    ]
    sedes = [
        {
            "nombre": "Sociedad Española",
            "superficie": "Cemento",
            "tipo_superficie": "cemento",
            "canchas": "2 canchas",
            "ilustracion": "img/landing-sociedad-espanola.png",
            "direccion": "Balcarce 643, Salta",
        },
        {
            "nombre": "Unión Sirio Libanesa",
            "superficie": "Polvo de ladrillo",
            "tipo_superficie": "ladrillo",
            "canchas": "2 canchas",
            "ilustracion": "img/landing-union-sirio-libanesa.png",
            "direccion": "San Martin 673, Salta",
        },
    ]
    return render(request, "landing.html", {
        "modalidades": modalidades,
        "sedes": sedes,
        "url_reservar": url_reservas,
    })


@require_GET
def privacidad(request):
    return render(request, "legal.html", {
        "titulo": "Política de privacidad",
        "texto": "Próximamente",
    })


@require_GET
def terminos(request):
    return render(request, "legal.html", {
        "titulo": "Términos y condiciones",
        "texto": "Próximamente",
    })


@login_required
@never_cache
def inicio(request):
    administrador = request.user.tiene_rol(Rol.ADMINISTRADOR)
    contexto = {"puede_reservar": request.user.puede_reservar}
    if administrador:
        ahora = timezone.localtime()
        limite = ahora + timedelta(hours=1)
        proxima_hora = (
            (Q(turno__fecha__gt=ahora.date()) | Q(turno__fecha=ahora.date(), turno__hora_inicio__gte=ahora.time()))
            & (Q(turno__fecha__lt=limite.date()) | Q(turno__fecha=limite.date(), turno__hora_inicio__lt=limite.time()))
            & Q(estado=Evento.Estado.PROGRAMADO)
        )
        actividad = Evento.objects.filter(
            tipo__in=(Evento.Tipo.CLASE, Evento.Tipo.RESERVA),
            turno__fecha__range=(ahora.date(), limite.date()),
        ).exclude(estado=Evento.Estado.ANULADO).aggregate(
            hoy=Count("pk", filter=Q(turno__fecha=ahora.date())),
            clases=Count("pk", filter=proxima_hora & Q(tipo=Evento.Tipo.CLASE)),
            reservas=Count("pk", filter=proxima_hora & Q(tipo=Evento.Tipo.RESERVA)),
        )
        mes_actual = ahora.date().replace(day=1)
        apertura, cierre = ventana_continuidad(mes_actual)
        encuestas_abiertas = ahora >= apertura
        fecha_limite = cierre if encuestas_abiertas else apertura
        if ahora < apertura:
            _, cierre_anterior = ventana_continuidad(mes_actual - timedelta(days=1))
            if ahora < cierre_anterior:
                encuestas_abiertas = True
                fecha_limite = cierre_anterior
        dias_encuestas = (fecha_limite.date() - ahora.date()).days
        usuarios = Usuario.objects.aggregate(
            total=Count("pk"), nuevos_hoy=Count("pk", filter=Q(date_joined__date=ahora.date())),
        )
        contexto.update({
            "hoy": ahora.date(), "actividad": actividad, "mes_actual": mes_actual,
            "alumnos_con_plan": PlanUsuario.objects.filter(
                mes_cubierto=mes_actual, estado=PlanUsuario.Estado.ACTIVO,
            ).values("usuario_id").distinct().count(),
            "socios": MembresiaUsuario.objects.filter(
                mes_cubierto=mes_actual, estado=MembresiaUsuario.Estado.ACTIVO,
            ).values("usuario_id").distinct().count(),
            "encuestas": {"dias": dias_encuestas, "abiertas": encuestas_abiertas},
            "usuarios": usuarios,
        })
    else:
        contexto.update(contexto_inicio_portal(request.user))
    return render(request, "inicio_administracion.html" if administrador else "inicio_portal.html", contexto)
