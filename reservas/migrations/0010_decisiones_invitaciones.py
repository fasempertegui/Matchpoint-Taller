from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def preparar_invitaciones(apps, schema_editor):
    invitado = apps.get_model("reservas", "ReservaInvitado")
    consulta = invitado.objects.using(schema_editor.connection.alias)
    consulta.filter(estado="retirado").delete()
    consulta.filter(respuesta_modificada_en__isnull=False).update(
        respondido_por=models.F("respuesta_modificada_por"), respondido_en=models.F("respuesta_modificada_en"),
    )
    ahora = timezone.localtime()
    futuras = models.Q(reserva__evento__turno__fecha__gt=ahora.date()) | models.Q(
        reserva__evento__turno__fecha=ahora.date(), reserva__evento__turno__hora_inicio__gt=ahora.time(),
    )
    consulta.filter(futuras, reserva__evento__estado="programado").exclude(respuesta="afirmativa").update(
        condicion_aplicada="sin_aplicar", membresia_usuario=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('membresias', '0013_ajustes_horas'),
        ('reservas', '0009_beneficio_invitados'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='reservainvitado',
            name='invitado_retiro_coherente',
        ),
        migrations.RemoveConstraint(
            model_name='reservainvitado',
            name='reservas_reservainvitado_respuesta_coherente',
        ),
        migrations.RemoveConstraint(
            model_name='reservainvitado',
            name='invitado_condicion_coherente',
        ),
        migrations.RunPython(preparar_invitaciones),
        # Validar referencias modificadas antes de alterar la tabla.
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='estado',
        ),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='respuesta_inicial',
        ),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='respuesta_modificada_en',
        ),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='respuesta_modificada_por',
        ),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='retirado_en',
        ),
        migrations.RemoveField(
            model_name='reservainvitado',
            name='retirado_por',
        ),
        migrations.AlterField(
            model_name='reservainvitado',
            name='condicion_aplicada',
            field=models.CharField(choices=[('sin_aplicar', 'Sin aplicar'), ('socio', 'Socio con beneficio'), ('no_socio', 'No socio'), ('cupo_agotado', 'Socio con cupo de invitado agotado'), ('reserva_normal', 'Reserva normal')], default='sin_aplicar', max_length=20),
        ),
        migrations.AlterField(
            model_name='reservainvitado',
            name='respuesta',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('afirmativa', 'Aceptada'), ('negativa', 'Rechazada')], default='pendiente', max_length=10),
        ),
        migrations.AddConstraint(
            model_name='reservainvitado',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('respondido_en__isnull', True), ('respondido_por__isnull', True), ('respuesta', 'pendiente')), models.Q(('respondido_en__isnull', False), ('respondido_por', models.F('usuario')), ('respondido_por__isnull', False), ('respuesta__in', ('afirmativa', 'negativa'))), _connector='OR'), name='invitado_respuesta_coherente'),
        ),
        migrations.AddConstraint(
            model_name='reservainvitado',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('condicion_aplicada__in', ('socio', 'cupo_agotado')), ('membresia_usuario__isnull', False)), models.Q(('condicion_aplicada__in', ('no_socio', 'reserva_normal', 'sin_aplicar')), ('membresia_usuario__isnull', True)), _connector='OR'), name='invitado_condicion_coherente'),
        ),
    ]
