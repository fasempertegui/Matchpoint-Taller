from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("instalaciones", "0004_precio_reserva_vigente"),
        ("reservas", "0006_finalizacion_automatica"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reserva",
            name="precio_reserva",
        ),
        migrations.AddField(
            model_name="reserva",
            name="precio_por_turno_aplicado",
            field=models.DecimalField(
                "Precio por turno aplicado (ARS)",
                max_digits=12,
                decimal_places=2,
                validators=[MinValueValidator(Decimal("0.01"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="reserva",
            constraint=models.CheckConstraint(
                condition=models.Q(precio_por_turno_aplicado__gte=Decimal("0.01")),
                name="reserva_precio_por_turno_positivo",
            ),
        ),
        migrations.DeleteModel(name="PrecioReserva"),
    ]
