from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Case, Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from .ingresos import ORIGENES
from .models import AjusteImporte, MovimientoFondo


CAMPOS_DEVOLUCION = ("concepto", "monto", "medio_pago", "referencia", "verificado", "destinatario", "operacion_id")


def anotar_situacion_financiera(consulta, tipo):
    from reservas.models import ReservaInvitado

    campo = ORIGENES[tipo][1]
    decimal = DecimalField(max_digits=20, decimal_places=2)
    movimientos = MovimientoFondo.objects.filter(**{campo: OuterRef("pk")}, estado="vigente").order_by().values(campo).annotate(
        neto=Sum(Case(
            When(clase="ingreso", then=F("monto")),
            When(clase="egreso", categoria_egreso="devoluciones", then=-F("monto")),
            default=Value(Decimal("0.00")), output_field=decimal,
        )),
    )
    importe_base = F("precio_aplicado")
    if tipo == "reserva":
        adicionales = ReservaInvitado.objects.filter(
            reserva_id=OuterRef("pk"), respuesta__in=("pendiente", "afirmativa"), condicion_aplicada__in=("no_socio", "cupo_agotado"),
        ).order_by().values("reserva_id").annotate(cantidad=Count("usuario_id"))
        importe_base = Case(
            When(membresia_usuario__isnull=True, then=F("precio_por_turno_aplicado")),
            default=F("precio_invitado_aplicado") * Coalesce(Subquery(adicionales.values("cantidad")), 0), output_field=decimal,
        )
    ajustes = AjusteImporte.objects.filter(**{campo: OuterRef("pk")}).order_by("-creado_en", "-pk")
    return consulta.annotate(
        importe_financiero=Coalesce(Subquery(ajustes.values("importe_nuevo")[:1]), importe_base, output_field=decimal),
        neto_financiero=Coalesce(Subquery(movimientos.values("neto")), Value(Decimal("0.00")), output_field=decimal),
    ).annotate(pendiente_cobro=F("importe_financiero") - F("neto_financiero"))


def origenes_con_pendiente(consulta, tipo):
    return anotar_situacion_financiera(consulta, tipo).filter(pendiente_cobro__gt=0)


def situacion_financiera(tipo, origen_id):
    movimientos = MovimientoFondo.objects.filter(**{ORIGENES[tipo][1]: origen_id}, estado="vigente")
    totales = movimientos.aggregate(
        ingresos=Sum("monto", filter=Q(clase="ingreso"), default=Decimal("0.00")),
        devoluciones=Sum("monto", filter=Q(clase="egreso", categoria_egreso="devoluciones"), default=Decimal("0.00")),
    )
    neto = totales["ingresos"] - totales["devoluciones"]
    return {**totales, "neto_recibido": neto}


def resumen_financiero(tipo, origen):
    situacion = situacion_financiera(tipo, origen.pk)
    importe = origen.importe_acordado
    anulado = origen.evento.estado == "anulado" if tipo == "reserva" else origen.estado == "anulado"
    diferencia = situacion["neto_recibido"] - importe
    estado = None
    if not anulado:
        estado = "Falta cobrar" if diferencia < 0 else "Excedente por resolver" if diferencia > 0 else "Cubierto"
    return {
        **situacion, "importe_acordado": importe, "operacion_anulada": anulado,
        "estado_financiero": estado, "diferencia_importe": abs(diferencia),
        "maximo_ingreso": max(Decimal("0.00"), -diferencia) if not anulado else Decimal("0.00"),
        "maximo_devolucion": max(Decimal("0.00"), situacion["neto_recibido"] if anulado else diferencia),
        "diferencia_revision": max(Decimal("0.00"), -situacion["neto_recibido"]),
    }


def _datos_revision(actor, sesion_id, tipo, origen_id, datos, situacion):
    campos = {campo: datos.get(campo, "") for campo in CAMPOS_DEVOLUCION}
    campos["monto"] = format(Decimal(campos["monto"]), ".2f")
    campos["operacion_id"] = str(campos["operacion_id"])
    saldo = {campo: format(situacion[campo], ".2f") for campo in ("ingresos", "devoluciones", "neto_recibido", "importe_acordado", "maximo_devolucion")}
    return {"actor": actor.pk, "sesion": sesion_id, "tipo": tipo, "origen": origen_id, "datos": campos, "situacion": saldo}


def revision_devolucion(actor, sesion_id, tipo, origen_id, datos, situacion):
    return signing.dumps(_datos_revision(actor, sesion_id, tipo, origen_id, datos, situacion), salt="caja.devolucion", compress=True)


def leer_revision_devolucion(actor, sesion_id, token):
    try:
        firmado = signing.loads(token, salt="caja.devolucion", max_age=900)
        if firmado["actor"] != actor.pk or firmado["sesion"] != sesion_id:
            raise signing.BadSignature
        return firmado
    except (signing.BadSignature, KeyError, TypeError):
        raise ValidationError("La revisión de la devolución venció o no es válida. Revisá nuevamente.") from None


def validar_revision_devolucion(actor, sesion_id, tipo, origen_id, datos, situacion, token):
    firmado = leer_revision_devolucion(actor, sesion_id, token)
    if firmado != _datos_revision(actor, sesion_id, tipo, origen_id, datos, situacion):
        raise ValidationError("La devolución o el neto recibido cambió. Revisá nuevamente el máximo disponible.")
