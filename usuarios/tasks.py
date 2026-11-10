from celery import shared_task
from django.conf import settings

from .limpieza import limpiar_cuentas_sin_verificar


@shared_task(acks_late=True, reject_on_worker_lost=True)
def limpiar_cuentas_iniciales():
    if not settings.CUENTAS_LIMPIEZA_HABILITADA:
        return 0
    return limpiar_cuentas_sin_verificar()
