from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from instalaciones.models import Cancha, Sede
from usuarios.models import Rol

from .actividad_mensual import contexto_mi_actividad_mensual
from .inicio_administracion import contexto_inicio_administracion
from .inicio_portal import contexto_inicio_portal


def _ilustracion_sede_portada(nombre):
    texto = nombre.lower()
    if "española" in texto or "espanola" in texto:
        return "img/landing-sociedad-espanola.png"
    if "sirio" in texto:
        return "img/landing-union-sirio-libanesa.png"
    return "img/sedes-geometria.svg"


def _sedes_destacadas_portada():
    sedes_activas = (
        Sede.objects.filter(estado=Sede.Estado.ACTIVA)
        .prefetch_related("canchas")
        .order_by("pk")
    )
    tarjetas = []
    for sede in sedes_activas:
        canchas_activas = [
            cancha for cancha in sede.canchas.all() if cancha.estado == Cancha.Estado.ACTIVA
        ]
        cantidad = len(canchas_activas)
        superficies = {cancha.superficie for cancha in canchas_activas}
        if superficies == {Cancha.Superficie.CEMENTO}:
            superficie = "Cemento"
            tipo_superficie = "cemento"
        elif superficies == {Cancha.Superficie.POLVO_LADRILLO}:
            superficie = "Polvo de ladrillo"
            tipo_superficie = "ladrillo"
        elif superficies:
            superficie = "Cemento y polvo de ladrillo"
            tipo_superficie = "cemento"
        else:
            superficie = ""
            tipo_superficie = ""

        tarjetas.append(
            {
                "nombre": sede.nombre,
                "direccion": sede.direccion_sin_cpa,
                "url_como_llegar": sede.url_como_llegar,
                "canchas": (
                    f"{cantidad} {'cancha' if cantidad == 1 else 'canchas'}"
                    if cantidad
                    else ""
                ),
                "superficie": superficie,
                "tipo_superficie": tipo_superficie,
                "ilustracion": _ilustracion_sede_portada(sede.nombre),
            }
        )
    return tarjetas


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
    sedes = _sedes_destacadas_portada()
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
        contexto.update(contexto_inicio_administracion(request.user))
    else:
        contexto.update(contexto_inicio_portal(request.user))
    return render(request, "inicio_administracion.html" if administrador else "inicio_portal.html", contexto)


@login_required
@never_cache
@require_GET
def mi_actividad_mensual(request):
    return render(request, "mi_actividad_mensual.html", contexto_mi_actividad_mensual(request))
