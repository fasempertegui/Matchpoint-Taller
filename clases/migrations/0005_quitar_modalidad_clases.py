from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clases', '0004_integridad_y_auditoria_clases'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='clase',
            name='clase_modalidad_valida',
        ),
        migrations.RemoveConstraint(
            model_name='turnoplanilla',
            name='turno_planilla_modalidad_valida',
        ),
        migrations.RemoveField(
            model_name='clase',
            name='modalidad',
        ),
        migrations.RemoveField(
            model_name='turnoplanilla',
            name='modalidad',
        ),
    ]
