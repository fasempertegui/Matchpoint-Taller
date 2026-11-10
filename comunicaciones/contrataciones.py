from django.urls import reverse
from django.utils.formats import date_format

from membresias.continuidad import encuesta_abierta, ventana_continuidad
from membresias.fechas import mes_siguiente

from .mensajes import dato_fecha, dato_importe
from .models import EnvioEmail
from .servicios import encolar_email


def avisar_contratacion(contratacion, tipo):
    parrafos = ["Administración registró tu contratación. Esta confirmación no acredita un pago."]
    incluye_encuesta = encuesta_abierta(contratacion)
    if incluye_encuesta:
        _, cierre = ventana_continuidad(contratacion.mes_cubierto)
        parrafos.append(
            f"Ya podés responder la encuesta sobre {date_format(mes_siguiente(contratacion.mes_cubierto), 'F Y')}. "
            f"Podés responder hasta terminar el día 5 de {date_format(cierre, 'F')}, desde el detalle de tu contratación."
        )
    return encolar_email(
        clave=f"contratacion:{tipo}:{contratacion.pk}", tipo=EnvioEmail.Tipo.CONTRATACION,
        destinatario=contratacion.usuario.email,
        datos={
            "vigencia": {"usuario_id": contratacion.usuario_id, "contratacion": {"tipo": tipo, "id": contratacion.pk}, "incluye_encuesta": incluye_encuesta},
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


def avisar_anulacion_contratacion(contratacion, tipo):
    return encolar_email(
        clave=f"contratacion_anulada:{tipo}:{contratacion.pk}", tipo=EnvioEmail.Tipo.CONTRATACION_ANULADA,
        destinatario=contratacion.usuario.email,
        datos={"vigencia": {"usuario_id": contratacion.usuario_id, "contratacion": {"tipo": tipo, "id": contratacion.pk}},
               "mensaje": {"parrafos": ["Tu contratación fue anulada. Esto no registra una devolución de dinero."],
                           "datos": [{"etiqueta": "Producto", "valor": contratacion.producto.nombre}, dato_fecha("Mes cubierto", contratacion.mes_cubierto)],
                           "acciones": [{"texto": "Ver contratación", "ruta": reverse(f"membresias:mi_{tipo}_contratado", args=[contratacion.pk])}]}})


def avisar_ajuste(ajuste):
    contrato = ajuste.membresia_usuario
    return encolar_email(
        clave=f"ajuste_horas:{ajuste.pk}", tipo=EnvioEmail.Tipo.AJUSTE_HORAS, destinatario=contrato.usuario.email,
        datos={"vigencia": {"usuario_id": contrato.usuario_id}, "mensaje": {
            "parrafos": ["Se registró una reversión de horas." if ajuste.reversion_de_id else "Se registró un ajuste de horas."],
            "datos": [{"etiqueta": "Producto", "valor": contrato.producto.nombre},
                      {"etiqueta": "Horas", "valor": ajuste.get_tipo_horas_display()},
                      {"etiqueta": "Operación", "valor": ajuste.get_operacion_display()},
                      {"etiqueta": "Cantidad", "valor": str(ajuste.cantidad)}, {"etiqueta": "Motivo", "valor": ajuste.motivo}],
            "acciones": [{"texto": "Ver mis horas", "ruta": reverse("membresias:mi_membresia_contratado", args=[contrato.pk])}],
        }})
