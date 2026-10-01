from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PrecioReserva(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    duracion_horas = models.PositiveSmallIntegerField(
        "Duración en horas",
        validators=[MinValueValidator(1), MaxValueValidator(24)],
    )
    precio_vigente = models.DecimalField(
        "Importe (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Importe total para la duración indicada.",
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "precios_reservas_cancha"
        ordering = ("duracion_horas", "-creado_en")
        default_permissions = ("add", "change", "view")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duracion_horas__gte=1),
                name="precio_reserva_duracion_positiva",
            ),
            models.CheckConstraint(
                condition=models.Q(duracion_horas__lte=24),
                name="precio_reserva_duracion_maxima",
            ),
            models.CheckConstraint(
                condition=models.Q(precio_vigente__gte=Decimal("0.01")),
                name="precio_reserva_importe_positivo",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")),
                name="precio_reserva_estado_valido",
            ),
            models.UniqueConstraint(
                fields=("duracion_horas",),
                condition=models.Q(estado="activo"),
                name="precio_reserva_duracion_activa_unica",
                violation_error_message="Ya existe una tarifa activa para esa duración.",
            ),
        ]
        verbose_name = "precio de reserva"
        verbose_name_plural = "precios de reservas"

    def __str__(self):
        unidad = "hora" if self.duracion_horas == 1 else "horas"
        return f"Reserva de {self.duracion_horas} {unidad}"
