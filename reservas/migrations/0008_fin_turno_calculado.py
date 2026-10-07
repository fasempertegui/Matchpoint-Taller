from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0007_precio_por_turno_aplicado"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="turno",
            name="turno_horario_valido",
        ),
        migrations.RemoveField(
            model_name="turno",
            name="hora_fin",
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.CheckConstraint(
                condition=models.Q(hora_inicio__in=tuple(time(hora) for hora in range(23))),
                name="turno_horario_valido",
                violation_error_message="El turno debe comenzar en punto entre las 00:00 y las 22:00.",
            ),
        ),
    ]
