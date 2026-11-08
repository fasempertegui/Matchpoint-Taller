from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum

from .ingresos import ORIGENES
from .models import MovimientoFondo


CAMPOS_DEVOLUCION = ("concepto", "monto", "medio_pago", "referencia", "verificado", "destinatario", "operacion_id")


def situacion_financiera(tipo, origen_id):
    movimientos = MovimientoFondo.objects.filter(**{ORIGENES[tipo][1]: origen_id}, estado="vigente")
    totales = movimientos.aggregate(
        ingresos=Sum("monto", filter=Q(clase="ingreso"), default=Decimal("0.00")),
        devoluciones=Sum("monto", filter=Q(clase="egreso", categoria_egreso="devoluciones"), default=Decimal("0.00")),
    )
    neto = totales["ingresos"] - totales["devoluciones"]
    return {**totales, "neto_recibido": neto, "maximo_devolucion": max(Decimal("0.00"), neto)}


def _datos_revision(actor, sesion_id, tipo, origen_id, datos, situacion):
    campos = {campo: datos.get(campo, "") for campo in CAMPOS_DEVOLUCION}
    campos["monto"] = format(Decimal(campos["monto"]), ".2f")
    campos["operacion_id"] = str(campos["operacion_id"])
    saldo = {campo: format(valor, ".2f") for campo, valor in situacion.items()} if situacion else None
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
