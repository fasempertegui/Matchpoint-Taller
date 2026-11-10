from django.db import migrations


def trasladar_cobertura(apps, schema_editor):
    alias = schema_editor.connection.alias
    asignacion = apps.get_model('clases', 'ClaseAlumno')
    envio = apps.get_model('comunicaciones', 'EnvioEmail')
    for fila in asignacion.objects.using(alias).filter(recordatorio_enviado=True).select_related('usuario', 'clase').iterator():
        envio.objects.using(alias).get_or_create(
            clave=f'recordatorio_clase:participante:{fila.identidad}',
            defaults={
                'tipo': 'recordatorio_clase', 'destinatario': fila.usuario.email, 'estado': 'descartado',
                'error_resumido': 'La participación ya tiene cobertura de recordatorio registrada.',
                'datos': {'vigencia': {'usuario_id': fila.usuario_id, 'evento_id': fila.clase.evento_id,
                                      'participacion': {'tipo': 'participante', 'actividad_id': fila.clase_id, 'identidad': str(fila.identidad)}},
                          'mensaje': {'parrafos': ['Cobertura de recordatorio registrada para esta participación.']}},
            },
        )


class Migration(migrations.Migration):
    dependencies = [('clases', '0010_identidad_asignaciones'), ('comunicaciones', '0001_initial')]
    operations = [
        migrations.RunPython(trasladar_cobertura, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(model_name='clasealumno', name='recordatorio_enviado'),
    ]
