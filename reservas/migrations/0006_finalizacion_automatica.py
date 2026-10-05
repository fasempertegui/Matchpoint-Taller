from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0005_modelo_reservas"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="reserva",
            name="reserva_estado_y_auditoria_validos",
        ),
        migrations.RemoveField(
            model_name="reserva",
            name="finalizado_por",
        ),
        migrations.AddConstraint(
            model_name="reserva",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        estado="programada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="anulada",
                        anulado_en__isnull=False,
                        anulado_por__isnull=False,
                        motivo_anulacion__regex=r"\S",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="finalizada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=False,
                    )
                ),
                name="reserva_estado_y_auditoria_validos",
                violation_error_message="Los datos de anulación y finalización deben corresponder al estado de la reserva. La anulación requiere un motivo.",
            ),
        ),
    ]
