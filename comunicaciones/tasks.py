from celery import shared_task

from .servicios import procesar_envios


@shared_task(acks_late=True, reject_on_worker_lost=True)
def entregar_email(envio_id):
    return procesar_envios(envio_id=envio_id, limite=1)


@shared_task(acks_late=True, reject_on_worker_lost=True)
def barrer_emails_pendientes():
    return procesar_envios()
