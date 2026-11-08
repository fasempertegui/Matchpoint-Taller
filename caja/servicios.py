from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from auditoria.contexto import contexto_auditoria
from usuarios.models import Rol, Usuario

from .models import MovimientoFondo, SesionCaja


def exigir_acceso_caja(actor, *, bloquear=False):
    if actor is None or not actor.is_authenticated:
        raise PermissionDenied
    consulta = Usuario.objects.select_for_update() if bloquear else Usuario.objects.all()
    usuario = consulta.filter(pk=actor.pk, is_active=True, debe_cambiar_contrasena=False).first()
    if usuario is None or not usuario.tiene_rol(Rol.ADMINISTRADOR):
        raise PermissionDenied
    return usuario


def ultimo_cierre():
    return SesionCaja.objects.filter(estado=SesionCaja.Estado.CERRADA).order_by("-cerrada_en", "-pk").first()


def _referencia_apertura(actor, cierre):
    return {"actor": actor.pk, "cierre": cierre.pk if cierre else None,
            "contado": str(cierre.efectivo_contado) if cierre else None}


def revision_apertura(actor, cierre):
    return signing.dumps(_referencia_apertura(actor, cierre), salt="caja.apertura")


def _validar_importe(campo, valor):
    if isinstance(valor, float):
        raise ValidationError("Ingresá un importe en pesos con hasta dos decimales.")
    importe = SesionCaja._meta.get_field(campo).clean(valor, None)
    if importe is None:
        raise ValidationError("El importe es obligatorio.")
    return importe


def efectivo_esperado(sesion):
    totales = sesion.movimientos.filter(estado="vigente", medio_pago="efectivo").aggregate(
        entradas=Sum("monto", filter=Q(clase__in=("ingreso", "aporte"))),
        salidas=Sum("monto", filter=Q(clase__in=("egreso", "retiro"))),
    )
    return sesion.efectivo_inicial + (totales["entradas"] or 0) - (totales["salidas"] or 0)


@transaction.atomic
def abrir_caja(actor, *, efectivo_inicial, motivo_apertura="", revision):
    actor = exigir_acceso_caja(actor, bloquear=True)
    if SesionCaja.objects.filter(estado=SesionCaja.Estado.ABIERTA).exists():
        raise ValidationError("Ya existe una sesión de caja abierta. Consultala antes de continuar.")
    inicial = _validar_importe("efectivo_inicial", efectivo_inicial)
    cierre = ultimo_cierre()
    try:
        datos = signing.loads(revision, salt="caja.apertura", max_age=900)
    except (signing.BadSignature, TypeError):
        raise ValidationError("La revisión de apertura venció o no es válida. Revisá nuevamente.") from None
    if datos != _referencia_apertura(actor, cierre):
        raise ValidationError("Cambió el último cierre. Revisá su contado antes de abrir caja.")
    motivo = motivo_apertura.strip() if cierre and inicial != cierre.efectivo_contado else ""
    if cierre and inicial != cierre.efectivo_contado and not motivo:
        raise ValidationError("El inicial difiere del último contado. Explicá el motivo de apertura.")
    sesion = SesionCaja(responsable=actor, efectivo_inicial=inicial, motivo_apertura=motivo)
    try:
        with transaction.atomic(), contexto_auditoria(actor):
            sesion.full_clean(validate_constraints=False)
            sesion.save()
            if datos != _referencia_apertura(actor, ultimo_cierre()):
                raise ValidationError("Cambió el último cierre. Revisá nuevamente antes de abrir.")
    except IntegrityError:
        if not SesionCaja.objects.filter(estado=SesionCaja.Estado.ABIERTA).exists():
            raise
        raise ValidationError("Otra solicitud abrió caja. Consultá la sesión abierta.") from None
    return sesion


@transaction.atomic
def cerrar_caja(actor, sesion_id, *, efectivo_contado, motivo_diferencia=""):
    actor = exigir_acceso_caja(actor, bloquear=True)
    sesion = SesionCaja.objects.select_for_update().get(pk=sesion_id)
    if sesion.responsable_id != actor.pk:
        raise PermissionDenied
    if sesion.estado != SesionCaja.Estado.ABIERTA:
        raise ValidationError("La sesión ya está cerrada y no admite modificaciones.")
    contado = _validar_importe("efectivo_contado", efectivo_contado)
    esperado = efectivo_esperado(sesion)
    diferencia = contado - esperado
    motivo = motivo_diferencia.strip() if diferencia else ""
    if diferencia and not motivo:
        raise ValidationError("El contado difiere del esperado. Explicá la diferencia para cerrar.")
    sesion.estado = SesionCaja.Estado.CERRADA
    sesion.cerrada_en = timezone.now()
    sesion.efectivo_esperado = esperado
    sesion.efectivo_contado = contado
    sesion.diferencia = diferencia
    sesion.motivo_diferencia = motivo
    sesion.full_clean()
    with contexto_auditoria(actor):
        sesion.save(update_fields=["estado", "cerrada_en", "efectivo_esperado", "efectivo_contado", "diferencia", "motivo_diferencia"])
    return sesion


def movimientos_validos_sesion(sesion):
    consulta = sesion.movimientos.all()
    if sesion.estado == SesionCaja.Estado.CERRADA:
        return consulta.filter(Q(anulado_en__isnull=True) | Q(anulado_en__gt=sesion.cerrada_en))
    return consulta.filter(estado=MovimientoFondo.Estado.VIGENTE)


def resumen_sesion(sesion):
    consulta = movimientos_validos_sesion(sesion)
    clases = dict(MovimientoFondo.Clase.choices)
    medios = dict(MovimientoFondo.Medio.choices)
    categorias = dict(MovimientoFondo.CategoriaIngreso.choices)
    totales = list(consulta.values("clase", "medio_pago").annotate(total=Sum("monto")).order_by("clase", "medio_pago"))
    for fila in totales:
        fila["clase_texto"] = clases[fila["clase"]]
        fila["medio_texto"] = medios[fila["medio_pago"]]
    ingresos = list(consulta.filter(clase="ingreso").values("categoria_ingreso").annotate(total=Sum("monto")).order_by("categoria_ingreso"))
    for fila in ingresos:
        fila["categoria_texto"] = categorias[fila["categoria_ingreso"]]
    egresos = consulta.filter(clase="egreso")
    gastos = egresos.exclude(categoria_egreso="devoluciones").aggregate(total=Sum("monto"))["total"] or 0
    devoluciones = egresos.filter(categoria_egreso="devoluciones").aggregate(total=Sum("monto"))["total"] or 0
    return {"resumen_medios": totales, "resumen_ingresos": ingresos, "gastos_operativos": gastos, "devoluciones": devoluciones}
