from django.db import models

from reservas.models import Evento


class Bloqueo(models.Model):
    class Motivo(models.TextChoices):
        CLIMA_ADVERSO = "clima_adverso", "Clima adverso"
        TORNEO = "torneo", "Torneo"
        MANTENIMIENTO = "mantenimiento", "Mantenimiento"

    id = models.BigAutoField(primary_key=True)
    evento = models.OneToOneField(
        Evento,
        on_delete=models.PROTECT,
        related_name="bloqueo",
        limit_choices_to={"tipo": Evento.Tipo.BLOQUEO},
    )
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    evento_origen = models.OneToOneField(
        Evento,
        on_delete=models.PROTECT,
        related_name="bloqueo_originado",
        null=True,
        blank=True,
        limit_choices_to={"tipo__in": (Evento.Tipo.RESERVA, Evento.Tipo.CLASE), "estado": Evento.Estado.ANULADO},
    )

    class Meta:
        db_table = "bloqueos"
        ordering = ("-evento__creado_en", "-pk")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(motivo__in=("clima_adverso", "torneo", "mantenimiento")),
                name="bloqueo_motivo_valido",
            ),
        ]
        verbose_name = "bloqueo"
        verbose_name_plural = "bloqueos"

    def __str__(self):
        return f"Bloqueo {self.pk}"

    @property
    def numero(self):
        return f"B-{self.pk:06d}" if self.pk is not None else ""
