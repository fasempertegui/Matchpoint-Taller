from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import OperationalError

from . import contrataciones

logger = get_task_logger(__name__)


@shared_task(
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(OperationalError,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 5},
)
def vencer_contrataciones():
    cantidades = contrataciones.vencer_contrataciones()
    logger.info(
        "Contrataciones vencidas automáticamente: %s planes y %s membresías",
        cantidades["planes"], cantidades["membresias"],
    )
    return cantidades


@shared_task(acks_late=True, reject_on_worker_lost=True, autoretry_for=(OperationalError,), retry_backoff=30, retry_kwargs={"max_retries": 5})
def avisar_continuidad():
    from django.conf import settings
    if not settings.EMAILS_TAREAS_PROGRAMADAS_HABILITADAS:
        return 0
    from comunicaciones.encuestas import encolar_encuestas_continuidad
    return encolar_encuestas_continuidad()
