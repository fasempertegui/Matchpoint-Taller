import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0001_precio_reserva'),
    ]

    operations = [
        migrations.AlterField(
            model_name='precioreserva',
            name='duracion_horas',
            field=models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(24)], verbose_name='Duración en horas'),
        ),
        migrations.AddConstraint(
            model_name='precioreserva',
            constraint=models.CheckConstraint(condition=models.Q(('duracion_horas__lte', 24)), name='precio_reserva_duracion_maxima'),
        ),
    ]
