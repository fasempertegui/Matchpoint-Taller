import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("reservas", "0008_fin_turno_calculado"),
    ]

    operations = [
        migrations.CreateModel(
            name="Evento",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tipo", models.CharField(max_length=10, choices=[("reserva", "Reserva"), ("clase", "Clase"), ("bloqueo", "Bloqueo")])),
                ("estado", models.CharField(max_length=10, default="programado", choices=[("programado", "Programado"), ("anulado", "Anulado"), ("finalizado", "Finalizado")])),
                ("observaciones", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("anulado_en", models.DateTimeField(blank=True, null=True)),
                ("motivo_anulacion", models.TextField(blank=True)),
                ("finalizado_en", models.DateTimeField(blank=True, null=True)),
                ("registrado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="eventos_registrados", to=settings.AUTH_USER_MODEL)),
                ("anulado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="eventos_anulados", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "eventos",
                "ordering": ("-creado_en", "-pk"),
                "default_permissions": (),
                "verbose_name": "evento",
                "verbose_name_plural": "eventos",
                "constraints": [
                    models.CheckConstraint(condition=models.Q(tipo__in=("reserva", "clase", "bloqueo")), name="evento_tipo_valido"),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                estado="programado",
                                anulado_por__isnull=True,
                                anulado_en__isnull=True,
                                motivo_anulacion="",
                                finalizado_en__isnull=True,
                            )
                            | models.Q(
                                estado="anulado",
                                anulado_por__isnull=False,
                                anulado_en__isnull=False,
                                motivo_anulacion__regex=r"\S",
                                finalizado_en__isnull=True,
                            )
                            | models.Q(
                                estado="finalizado",
                                anulado_por__isnull=True,
                                anulado_en__isnull=True,
                                motivo_anulacion="",
                                finalizado_en__isnull=False,
                            )
                        ),
                        name="evento_estado_y_auditoria_validos",
                        violation_error_message="Los datos de anulación y finalización deben corresponder al estado del evento.",
                    ),
                    models.CheckConstraint(condition=~models.Q(tipo="bloqueo", estado="finalizado"), name="evento_bloqueo_no_finalizado"),
                ],
            },
        ),
        migrations.CreateModel(
            name="EventoTurno",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("evento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles", to="reservas.evento")),
                ("turno", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vinculos_eventos", to="reservas.turno")),
            ],
            options={
                "db_table": "eventos_turnos",
                "ordering": ("turno__fecha", "turno__hora_inicio", "pk"),
                "default_permissions": (),
                "verbose_name": "turno de evento",
                "verbose_name_plural": "turnos de eventos",
                "constraints": [
                    models.UniqueConstraint(fields=("evento", "turno"), name="evento_turno_unico", violation_error_message="El turno ya está incluido en este evento."),
                ],
            },
        ),
        migrations.AddField(
            model_name="evento",
            name="turnos",
            field=models.ManyToManyField(related_name="eventos", through="reservas.EventoTurno", to="reservas.turno"),
        ),
        migrations.RemoveConstraint(model_name="reserva", name="reserva_estado_y_auditoria_validos"),
        migrations.AddField(
            model_name="reserva",
            name="evento",
            field=models.OneToOneField(limit_choices_to={"tipo": "reserva"}, on_delete=django.db.models.deletion.PROTECT, related_name="reserva", to="reservas.evento"),
        ),
        migrations.AddField(
            model_name="reserva",
            name="anulada_por_organizador",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="reserva",
            options={
                "ordering": ("-evento__creado_en", "-pk"),
                "default_permissions": ("add", "view"),
                "verbose_name": "reserva",
                "verbose_name_plural": "reservas",
            },
        ),
        migrations.RemoveField(model_name="reserva", name="registrado_por"),
        migrations.RemoveField(model_name="reserva", name="estado"),
        migrations.RemoveField(model_name="reserva", name="observaciones"),
        migrations.RemoveField(model_name="reserva", name="creado_en"),
        migrations.RemoveField(model_name="reserva", name="anulado_por"),
        migrations.RemoveField(model_name="reserva", name="anulado_en"),
        migrations.RemoveField(model_name="reserva", name="motivo_anulacion"),
        migrations.RemoveField(model_name="reserva", name="finalizado_en"),
        migrations.DeleteModel(name="ReservaTurno"),
    ]
