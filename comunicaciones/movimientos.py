from django.urls import reverse

from .mensajes import dato_importe
from .servicios import encolar_email


def avisar_movimiento(movimiento, origen, tipo):
    if origen is None or movimiento.clase not in ("ingreso", "egreso"):
        return
    usuario = origen.organizador if tipo == "reserva" else origen.usuario
    ruta = "reservas:reserva_detalle" if tipo == "reserva" else f"membresias:mi_{tipo}_contratado"
    encolar_email(clave=f"movimiento:{movimiento.pk}", tipo="movimiento", destinatario=usuario.email,
                  datos={"vigencia": {"usuario_id": usuario.pk}, "mensaje": {
                      "parrafos": ["Se registró un movimiento de dinero vinculado a tu reserva o contratación."],
                      "datos": [{"etiqueta": "Operación vinculada", "valor": f"{tipo.capitalize()} #{origen.pk}"}, {"etiqueta": "Tipo", "valor": movimiento.get_clase_display()}, dato_importe("Importe", movimiento.monto),
                                {"etiqueta": "Medio", "valor": movimiento.get_medio_pago_display()},
                                {"etiqueta": "Concepto", "valor": movimiento.concepto}],
                      "acciones": [{"texto": "Ver mi operación", "ruta": reverse(ruta, args=[origen.pk])}],
                  }})
