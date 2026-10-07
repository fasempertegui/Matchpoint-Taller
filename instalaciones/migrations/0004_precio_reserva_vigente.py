from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("instalaciones", "0003_horarios_en_punto_y_pausa_minima"),
    ]

    operations = [
        migrations.AddField(
            model_name="sede",
            name="precio_reserva_vigente",
            field=models.DecimalField(
                "Precio por turno (ARS)",
                max_digits=12,
                decimal_places=2,
                validators=[MinValueValidator(Decimal("0.01"))],
                blank=True,
                null=True,
                help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
            ),
        ),
        migrations.AddConstraint(
            model_name="sede",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(precio_reserva_vigente__isnull=True)
                    | models.Q(precio_reserva_vigente__gte=Decimal("0.01"))
                ),
                name="sede_precio_reserva_positivo",
                violation_error_message="El precio por turno debe ser positivo.",
            ),
        ),
    ]
