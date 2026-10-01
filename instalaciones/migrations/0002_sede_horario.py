import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instalaciones', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SedeHorario',
            fields=[
                ('pk', models.CompositePrimaryKey('sede_id', 'dia_semana', blank=True, editable=False, primary_key=True, serialize=False)),
                ('dia_semana', models.PositiveSmallIntegerField(choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')])),
                ('hora_inicio_1', models.TimeField(verbose_name='Inicio de la primera franja')),
                ('hora_fin_1', models.TimeField(verbose_name='Fin de la primera franja')),
                ('hora_inicio_2', models.TimeField(blank=True, null=True, verbose_name='Inicio de la segunda franja')),
                ('hora_fin_2', models.TimeField(blank=True, null=True, verbose_name='Fin de la segunda franja')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('sede', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='horarios', to='instalaciones.sede')),
            ],
            options={
                'verbose_name': 'horario de sede',
                'verbose_name_plural': 'horarios de sede',
                'db_table': 'sedes_horarios',
                'ordering': ('dia_semana',),
                'default_permissions': (),
                'constraints': [models.CheckConstraint(condition=models.Q(('dia_semana__gte', 1), ('dia_semana__lte', 7)), name='sede_horario_dia_valido'), models.CheckConstraint(condition=models.Q(('hora_fin_1__gt', models.F('hora_inicio_1'))), name='sede_horario_primera_franja_valida'), models.CheckConstraint(condition=models.Q(models.Q(('hora_fin_2__isnull', True), ('hora_inicio_2__isnull', True)), models.Q(('hora_fin_2__isnull', False), ('hora_inicio_2__isnull', False)), _connector='OR'), name='sede_horario_segunda_franja_completa'), models.CheckConstraint(condition=models.Q(('hora_inicio_2__isnull', True), ('hora_fin_2__gt', models.F('hora_inicio_2')), _connector='OR'), name='sede_horario_segunda_franja_valida'), models.CheckConstraint(condition=models.Q(('hora_inicio_2__isnull', True), ('hora_inicio_2__gte', models.F('hora_fin_1')), _connector='OR'), name='sede_horario_franjas_sin_superposicion')],
            },
        ),
    ]
