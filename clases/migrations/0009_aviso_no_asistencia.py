from django.conf import settings
from django.db import migrations, models


def convertir_avisos(apps, schema_editor):
    alumno = apps.get_model("clases", "ClaseAlumno")
    alias = schema_editor.connection.alias
    alumno.objects.using(alias).filter(respuesta_modificada_en__isnull=False).update(
        respondido_por=models.F("respuesta_modificada_por"),
        respondido_en=models.F("respuesta_modificada_en"),
    )
    alumno.objects.using(alias).filter(respuesta__in=("pendiente", "afirmativa")).update(respuesta="asistira")
    alumno.objects.using(alias).filter(respuesta="negativa").update(respuesta="no_asistira")


class Migration(migrations.Migration):

    dependencies = [
        ('clases', '0008_integridad_respuestas_resultado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='clasealumno',
            name='clases_clasealumno_respuesta_coherente',
        ),
        migrations.AlterField(
            model_name='clasealumno',
            name='respuesta',
            field=models.CharField(choices=[('asistira', 'Asistirá'), ('no_asistira', 'No asistirá')], default='asistira', max_length=11),
        ),
        migrations.RunPython(convertir_avisos),
        # Las referencias actualizadas deben validarse antes de alterar la tabla.
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop),
        migrations.RemoveField(
            model_name='clasealumno',
            name='respuesta_inicial',
        ),
        migrations.RemoveField(
            model_name='clasealumno',
            name='respuesta_modificada_en',
        ),
        migrations.RemoveField(
            model_name='clasealumno',
            name='respuesta_modificada_por',
        ),
        migrations.AddConstraint(
            model_name='clasealumno',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('respondido_en__isnull', True), ('respondido_por__isnull', True), ('respuesta', 'asistira')), models.Q(('respondido_en__isnull', False), ('respondido_por', models.F('usuario')), ('respondido_por__isnull', False), ('respuesta__in', ('asistira', 'no_asistira'))), _connector='OR'), name='clase_alumno_aviso_coherente'),
        ),
    ]
