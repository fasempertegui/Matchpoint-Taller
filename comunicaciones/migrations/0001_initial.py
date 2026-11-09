import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EnvioEmail',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('clave', models.CharField(max_length=250, unique=True)),
                ('tipo', models.CharField(choices=[('bienvenida', 'Bienvenida'), ('verificacion', 'Verificá tu correo'), ('recuperacion', 'Recuperá tu contraseña'), ('solicitud_correo', 'Solicitud de cambio de correo'), ('confirmar_correo', 'Confirmá tu nuevo correo'), ('correo_cambiado', 'Cambiaste tu correo'), ('estado_cuenta', 'Estado de tu cuenta'), ('contrasena_cambiada', 'Cambiaste tu contraseña'), ('reserva_creada', 'Reserva confirmada'), ('invitacion', 'Invitación a una reserva'), ('retirada_invitacion', 'Invitación retirada'), ('respuesta_invitacion', 'Respuesta a tu invitación'), ('reserva_anulada', 'Reserva anulada'), ('asignacion_clase', 'Asignación a una clase'), ('generacion_clases', 'Tus clases programadas'), ('retirada_clase', 'Asignación retirada'), ('cancha_cambiada', 'Nueva cancha para tu clase'), ('no_asisto', 'Aviso de no asistencia'), ('clase_anulada', 'Clase anulada'), ('contratacion', 'Contratación registrada'), ('contratacion_anulada', 'Contratación anulada'), ('ajuste_horas', 'Ajuste de horas'), ('movimiento', 'Movimiento registrado'), ('recordatorio_clase', 'Recordatorio de clase'), ('recordatorio_reserva', 'Recordatorio de reserva'), ('continuidad', 'Encuesta de continuidad')], max_length=32)),
                ('destinatario', models.EmailField(max_length=254)),
                ('datos', models.JSONField()),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('en_proceso', 'En proceso'), ('enviado', 'Enviado'), ('fallido', 'Fallido'), ('descartado', 'Descartado')], default='pendiente', max_length=12)),
                ('creado_en', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('proximo_intento_en', models.DateTimeField(default=django.utils.timezone.now)),
                ('intentos', models.PositiveSmallIntegerField(default=0)),
                ('ultimo_intento_en', models.DateTimeField(blank=True, null=True)),
                ('enlace_emitido_en', models.DateTimeField(blank=True, null=True)),
                ('reserva_token', models.UUIDField(blank=True, editable=False, null=True)),
                ('reservado_hasta', models.DateTimeField(blank=True, null=True)),
                ('aceptado_en', models.DateTimeField(blank=True, null=True)),
                ('error_resumido', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'db_table': 'envios_email',
                'ordering': ('-creado_en', '-pk'),
                'default_permissions': (),
                'indexes': [models.Index(fields=['estado', 'proximo_intento_en'], name='envios_pendientes_idx'), models.Index(fields=['estado', 'reservado_hasta'], name='envios_reservados_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('estado__in', ('pendiente', 'en_proceso', 'enviado', 'fallido', 'descartado'))), name='envio_estado_valido'), models.CheckConstraint(condition=models.Q(('intentos__lte', 4)), name='envio_intentos_validos'), models.CheckConstraint(condition=models.Q(models.Q(('estado', 'en_proceso'), ('reserva_token__isnull', False), ('reservado_hasta__isnull', False)), models.Q(models.Q(('estado', 'en_proceso'), _negated=True), ('reserva_token__isnull', True), ('reservado_hasta__isnull', True)), _connector='OR'), name='envio_reserva_coherente'), models.CheckConstraint(condition=models.Q(models.Q(('aceptado_en__isnull', False), ('estado', 'enviado')), models.Q(models.Q(('estado', 'enviado'), _negated=True), ('aceptado_en__isnull', True)), _connector='OR'), name='envio_aceptacion_coherente')],
            },
        ),
    ]
