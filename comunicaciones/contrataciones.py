from django.urls import reverse
from django.utils.formats import date_format

from membresias.continuidad import encuesta_abierta, ventana_continuidad
from membresias.fechas import mes_siguiente

from .mensajes import dato_fecha, dato_importe
from .models import EnvioEmail
from .servicios import encolar_email


def avisar_contratacion(contratacion, tipo):
    parrafos = ["Administración registró tu contratación. Esta confirmación no acredita un pago."]
    if encuesta_abierta(contratacion):
        _, cierre = ventana_continuidad(contratacion.mes_cubierto)
        parrafos.append(
            f"Ya podés responder la encuesta sobre {date_format(mes_siguiente(contratacion.mes_cubierto), 'F Y')}. "
            f"Podés responder hasta terminar el día 5 de {date_format(cierre, 'F')}, desde el detalle de tu contratación."
        )
    return encolar_email(
        clave=f"contratacion:{tipo}:{contratacion.pk}", tipo=EnvioEmail.Tipo.CONTRATACION,
        destinatario=contratacion.usuario.email,
        datos={
            "vigencia": {"usuario_id": contratacion.usuario_id, "contratacion": {"tipo": tipo, "id": contratacion.pk}},
            "mensaje": {
                "parrafos": parrafos,
                "datos": [
                    {"etiqueta": "Producto", "valor": contratacion.producto.nombre},
                    dato_fecha("Desde", contratacion.fecha_inicio), dato_fecha("Hasta", contratacion.fecha_fin),
                    dato_importe("Importe aplicado", contratacion.precio_aplicado),
                ],
                "acciones": [{"texto": "Ver mi contratación", "ruta": reverse(f"membresias:mi_{tipo}_contratado", args=[contratacion.pk])}],
            },
        },
    )
