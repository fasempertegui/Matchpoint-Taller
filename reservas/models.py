from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class PrecioReserva(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    sede = models.ForeignKey(
        "instalaciones.Sede",
        on_delete=models.PROTECT,
        related_name="precios_reservas",
    )
    importe = models.DecimalField(
        "Precio por turno (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
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
        ordering = ("sede__nombre", "-creado_en", "-pk")
        default_permissions = ("add", "change", "view")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(importe__gte=Decimal("0.01")),
                name="precio_reserva_importe_positivo",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")),
                name="precio_reserva_estado_valido",
            ),
            models.UniqueConstraint(
                fields=("sede",),
                condition=models.Q(estado="activo"),
                name="precio_reserva_sede_activo_unico",
                violation_error_message="Ya existe un precio activo para esta sede.",
            ),
        ]
        verbose_name = "precio de reserva"
        verbose_name_plural = "precios de reservas"

    def __str__(self):
        return f"Precio por turno ({self.sede.nombre})"
