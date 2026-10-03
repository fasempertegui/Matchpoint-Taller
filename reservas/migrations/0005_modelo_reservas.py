import datetime
import django.db.models.deletion
import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instalaciones', '0002_sede_horario'),
        ('reservas', '0004_precio_por_turno'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Reserva',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('estado', models.CharField(choices=[('programada', 'Programada'), ('finalizada', 'Finalizada'), ('anulada', 'Anulada')], default='programada', max_length=10)),
                ('observaciones', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('anulado_en', models.DateTimeField(blank=True, null=True)),
                ('motivo_anulacion', models.TextField(blank=True)),
                ('finalizado_en', models.DateTimeField(blank=True, null=True)),
                ('anulado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reservas_anuladas', to=settings.AUTH_USER_MODEL)),
                ('finalizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reservas_finalizadas', to=settings.AUTH_USER_MODEL)),
                ('organizador', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservas', to=settings.AUTH_USER_MODEL)),
                ('precio_reserva', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservas', to='reservas.precioreserva')),
                ('registrado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservas_registradas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'reserva',
                'verbose_name_plural': 'reservas',
                'db_table': 'reservas',
                'ordering': ('-creado_en', '-pk'),
                'default_permissions': ('add', 'view'),
            },
        ),
        migrations.CreateModel(
            name='Turno',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('fecha', models.DateField()),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('cancha', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='turnos', to='instalaciones.cancha')),
            ],
            options={
                'verbose_name': 'turno',
                'verbose_name_plural': 'turnos',
                'db_table': 'turnos',
                'ordering': ('fecha', 'hora_inicio', 'cancha_id'),
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='ReservaTurno',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('reserva', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='detalles', to='reservas.reserva')),
                ('turno', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reservas_turnos', to='reservas.turno')),
            ],
            options={
                'verbose_name': 'turno de reserva',
                'verbose_name_plural': 'turnos de reserva',
                'db_table': 'reservas_turnos',
                'ordering': ('turno__fecha', 'turno__hora_inicio', 'pk'),
                'default_permissions': (),
            },
        ),
        migrations.AddConstraint(
            model_name='reserva',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('anulado_en__isnull', True), ('anulado_por__isnull', True), ('estado', 'programada'), ('finalizado_en__isnull', True), ('finalizado_por__isnull', True), ('motivo_anulacion', '')), models.Q(('anulado_en__isnull', False), ('anulado_por__isnull', False), ('estado', 'anulada'), ('finalizado_en__isnull', True), ('finalizado_por__isnull', True), ('motivo_anulacion__regex', '\\S')), models.Q(('anulado_en__isnull', True), ('anulado_por__isnull', True), ('estado', 'finalizada'), ('finalizado_en__isnull', False), ('finalizado_por__isnull', False), ('motivo_anulacion', '')), _connector='OR'), name='reserva_estado_y_auditoria_validos', violation_error_message='Los datos de anulación y finalización deben corresponder al estado de la reserva. La anulación requiere un motivo.'),
        ),
        migrations.AddConstraint(
            model_name='turno',
            constraint=models.UniqueConstraint(fields=('cancha', 'fecha', 'hora_inicio'), name='turno_cancha_fecha_inicio_unico', violation_error_message='Ya existe un turno para esa cancha, fecha y hora.'),
        ),
        migrations.AddConstraint(
            model_name='turno',
            constraint=models.CheckConstraint(condition=models.Q(('hora_fin', django.db.models.expressions.CombinedExpression(models.F('hora_inicio'), '+', models.Value(datetime.timedelta(seconds=3600)))), ('hora_inicio__in', (datetime.time(0, 0), datetime.time(1, 0), datetime.time(2, 0), datetime.time(3, 0), datetime.time(4, 0), datetime.time(5, 0), datetime.time(6, 0), datetime.time(7, 0), datetime.time(8, 0), datetime.time(9, 0), datetime.time(10, 0), datetime.time(11, 0), datetime.time(12, 0), datetime.time(13, 0), datetime.time(14, 0), datetime.time(15, 0), datetime.time(16, 0), datetime.time(17, 0), datetime.time(18, 0), datetime.time(19, 0), datetime.time(20, 0), datetime.time(21, 0), datetime.time(22, 0)))), name='turno_horario_valido', violation_error_message='El turno debe durar una hora, comenzar en punto y terminar dentro de la misma fecha.'),
        ),
        migrations.AddConstraint(
            model_name='reservaturno',
            constraint=models.UniqueConstraint(fields=('reserva', 'turno'), name='reserva_turno_unico', violation_error_message='El turno ya está incluido en esta reserva.'),
        ),
    ]
