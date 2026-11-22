import datetime
import django.db.models.deletion
import django.db.models.expressions
import django.db.models.lookups
from django.db import migrations, models


HORAS_EN_PUNTO = tuple(datetime.time(hora, 0) for hora in range(24))


class Migration(migrations.Migration):

    dependencies = [
        ("instalaciones", "0001_initial"),
        ("auditoria", "0007_acciones_contrasena"),
    ]

    operations = [
        migrations.CreateModel(
            name="SedeHorarioEspecial",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("fecha", models.DateField()),
                ("motivo", models.CharField(max_length=150)),
                ("cerrada", models.BooleanField(default=False)),
                (
                    "hora_inicio_1",
                    models.TimeField(
                        blank=True,
                        null=True,
                        verbose_name="Inicio de la primera franja",
                    ),
                ),
                (
                    "hora_fin_1",
                    models.TimeField(
                        blank=True,
                        null=True,
                        verbose_name="Fin de la primera franja",
                    ),
                ),
                (
                    "hora_inicio_2",
                    models.TimeField(
                        blank=True,
                        null=True,
                        verbose_name="Inicio de la segunda franja",
                    ),
                ),
                (
                    "hora_fin_2",
                    models.TimeField(
                        blank=True,
                        null=True,
                        verbose_name="Fin de la segunda franja",
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="horarios_especiales",
                        to="instalaciones.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "horario especial de sede",
                "verbose_name_plural": "horarios especiales de sede",
                "db_table": "sedes_horarios_especiales",
                "ordering": ("fecha", "sede__nombre"),
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("sede", "fecha"),
                        name="sede_horario_especial_sede_fecha_unico",
                        violation_error_message="Ya existe un horario especial para esta sede en esa fecha.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("fecha__gte", datetime.date(2026, 8, 1))),
                        name="sede_horario_especial_fecha_operativa",
                        violation_error_message="La fecha no puede ser anterior al 01/08/2026.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(motivo__regex=r"\S"),
                        name="sede_horario_especial_motivo_informado",
                        violation_error_message="Indicá el motivo del horario especial.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("cerrada", True),
                                ("hora_fin_1__isnull", True),
                                ("hora_fin_2__isnull", True),
                                ("hora_inicio_1__isnull", True),
                                ("hora_inicio_2__isnull", True),
                            ),
                            models.Q(
                                ("cerrada", False),
                                ("hora_fin_1__isnull", False),
                                ("hora_inicio_1__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="sede_horario_especial_estado_franjas",
                        violation_error_message=(
                            "Si la sede está cerrada no debe tener franjas; "
                            "si está abierta debe tener al menos la primera franja."
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("hora_inicio_1__isnull", True),
                                ("hora_inicio_1__in", HORAS_EN_PUNTO),
                                _connector="OR",
                            ),
                            models.Q(
                                ("hora_fin_1__isnull", True),
                                ("hora_fin_1__in", HORAS_EN_PUNTO),
                                _connector="OR",
                            ),
                            models.Q(
                                ("hora_inicio_2__isnull", True),
                                ("hora_inicio_2__in", HORAS_EN_PUNTO),
                                _connector="OR",
                            ),
                            models.Q(
                                ("hora_fin_2__isnull", True),
                                ("hora_fin_2__in", HORAS_EN_PUNTO),
                                _connector="OR",
                            ),
                        ),
                        name="sede_horario_especial_horas_en_punto",
                        violation_error_message="Los horarios deben ser en punto.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("hora_inicio_1__isnull", True),
                            ("hora_fin_1__gt", models.F("hora_inicio_1")),
                            _connector="OR",
                        ),
                        name="sede_horario_especial_primera_franja_valida",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("hora_fin_2__isnull", True),
                                ("hora_inicio_2__isnull", True),
                            ),
                            models.Q(
                                ("hora_fin_2__isnull", False),
                                ("hora_inicio_2__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="sede_horario_especial_segunda_franja_completa",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("hora_inicio_2__isnull", True),
                            ("hora_fin_2__gt", models.F("hora_inicio_2")),
                            _connector="OR",
                        ),
                        name="sede_horario_especial_segunda_franja_valida",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("hora_inicio_2__isnull", True),
                            django.db.models.lookups.GreaterThanOrEqual(
                                django.db.models.expressions.CombinedExpression(
                                    models.F("hora_inicio_2"),
                                    "-",
                                    models.F("hora_fin_1"),
                                ),
                                models.Value(datetime.timedelta(seconds=3600)),
                            ),
                            _connector="OR",
                        ),
                        name="sede_horario_especial_pausa_minima",
                        violation_error_message="Debe haber al menos una hora sin funcionamiento entre las dos franjas.",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER auditar_sedes_horarios_especiales
                AFTER UPDATE OR DELETE ON sedes_horarios_especiales
                FOR EACH ROW EXECUTE FUNCTION registrar_auditoria('id');
            """,
            reverse_sql="DROP TRIGGER auditar_sedes_horarios_especiales ON sedes_horarios_especiales;",
        ),
    ]
