from datetime import time, timedelta

from django.db import migrations, models
from django.db.models.lookups import GreaterThanOrEqual


HORAS_EN_PUNTO = tuple(time(hora) for hora in range(24))


class Migration(migrations.Migration):
    dependencies = [
        ("instalaciones", "0002_sede_horario"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="sedehorario",
            name="sede_horario_franjas_sin_superposicion",
        ),
        migrations.AddConstraint(
            model_name="sedehorario",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        hora_inicio_1__in=HORAS_EN_PUNTO,
                        hora_fin_1__in=HORAS_EN_PUNTO,
                    )
                    & (
                        models.Q(hora_inicio_2__isnull=True)
                        | models.Q(hora_inicio_2__in=HORAS_EN_PUNTO)
                    )
                    & (
                        models.Q(hora_fin_2__isnull=True)
                        | models.Q(hora_fin_2__in=HORAS_EN_PUNTO)
                    )
                ),
                name="sede_horario_horas_en_punto",
                violation_error_message="Los horarios deben ser en punto.",
            ),
        ),
        migrations.AddConstraint(
            model_name="sedehorario",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True)
                    | GreaterThanOrEqual(
                        models.F("hora_inicio_2") - models.F("hora_fin_1"),
                        models.Value(timedelta(hours=1)),
                    )
                ),
                name="sede_horario_pausa_minima",
                violation_error_message="Debe haber al menos una hora sin funcionamiento entre las dos franjas.",
            ),
        ),
    ]
