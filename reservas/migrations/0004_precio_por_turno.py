from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


def validar_precios_por_hora(apps, schema_editor):
    PrecioReserva = apps.get_model("reservas", "PrecioReserva")
    precios = PrecioReserva.objects.using(schema_editor.connection.alias)
    if precios.exclude(duracion_horas=1).exists():
        raise RuntimeError(
            "Existen precios para duraciones distintas de una hora. "
            "Definí su tratamiento antes de aplicar la migración de precios por turno."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0003_precios_por_sede"),
    ]

    operations = [
        migrations.RunPython(validar_precios_por_hora),
        migrations.RemoveConstraint(
            model_name="precioreserva",
            name="precio_reserva_sede_duracion_activa_unica",
        ),
        migrations.RemoveConstraint(
            model_name="precioreserva",
            name="precio_reserva_duracion_positiva",
        ),
        migrations.RemoveConstraint(
            model_name="precioreserva",
            name="precio_reserva_duracion_maxima",
        ),
        migrations.RemoveConstraint(
            model_name="precioreserva",
            name="precio_reserva_importe_positivo",
        ),
        migrations.RenameField(
            model_name="precioreserva",
            old_name="precio_vigente",
            new_name="importe",
        ),
        migrations.RemoveField(
            model_name="precioreserva",
            name="duracion_horas",
        ),
        migrations.AlterField(
            model_name="precioreserva",
            name="importe",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
                max_digits=12,
                validators=[MinValueValidator(Decimal("0.01"))],
                verbose_name="Precio por turno (ARS)",
            ),
        ),
        migrations.AlterModelOptions(
            name="precioreserva",
            options={
                "default_permissions": ("add", "change", "view"),
                "ordering": ("sede__nombre", "-creado_en", "-pk"),
                "verbose_name": "precio de reserva",
                "verbose_name_plural": "precios de reservas",
            },
        ),
        migrations.AddConstraint(
            model_name="precioreserva",
            constraint=models.CheckConstraint(
                condition=models.Q(importe__gte=Decimal("0.01")),
                name="precio_reserva_importe_positivo",
            ),
        ),
        migrations.AddConstraint(
            model_name="precioreserva",
            constraint=models.UniqueConstraint(
                condition=models.Q(estado="activo"),
                fields=("sede",),
                name="precio_reserva_sede_activo_unico",
                violation_error_message="Ya existe un precio activo para esta sede.",
            ),
        ),
    ]
