from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import OperationalError

from . import servicios

logger = get_task_logger(__name__)


@shared_task(
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(OperationalError,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 5},
)
def finalizar_reservas_vencidas():
    cantidad = servicios.finalizar_reservas_vencidas()
    logger.info("Reservas finalizadas automáticamente: %s", cantidad)
    return cantidad
