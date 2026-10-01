import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PrecioReserva',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('duracion_horas', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name='Duración en horas')),
                ('precio_vigente', models.DecimalField(decimal_places=2, help_text='Importe total para la duración indicada.', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Importe (ARS)')),
                ('estado', models.CharField(choices=[('activo', 'Activo'), ('inactivo', 'Inactivo')], default='activo', max_length=10)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'precio de reserva',
                'verbose_name_plural': 'precios de reservas',
                'db_table': 'precios_reservas_cancha',
                'ordering': ('duracion_horas', '-creado_en'),
                'default_permissions': ('add', 'change', 'view'),
                'constraints': [models.CheckConstraint(condition=models.Q(('duracion_horas__gte', 1)), name='precio_reserva_duracion_positiva'), models.CheckConstraint(condition=models.Q(('precio_vigente__gte', Decimal('0.01'))), name='precio_reserva_importe_positivo'), models.CheckConstraint(condition=models.Q(('estado__in', ('activo', 'inactivo'))), name='precio_reserva_estado_valido'), models.UniqueConstraint(condition=models.Q(('estado', 'activo')), fields=('duracion_horas',), name='precio_reserva_duracion_activa_unica', violation_error_message='Ya existe una tarifa activa para esa duración.')],
            },
        ),
    ]
