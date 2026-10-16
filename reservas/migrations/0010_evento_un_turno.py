import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count, Min


def asignar_turnos(apps, schema_editor):
    Evento = apps.get_model("reservas", "Evento")
    EventoTurno = apps.get_model("reservas", "EventoTurno")
    alias = schema_editor.connection.alias
    eventos = Evento.objects.using(alias).annotate(
        cantidad_turnos=Count("detalles"),
        turno_asignado=Min("detalles__turno_id"),
    )
    invalidos = list(eventos.exclude(cantidad_turnos=1).values_list("pk", flat=True)[:10])
    if invalidos:
        raise RuntimeError(
            "Cada evento debe tener exactamente un turno. Revisá los eventos "
            f"{invalidos} antes de aplicar la migración. No se dividen ni eliminan reservas."
        )
    ocupados = EventoTurno.objects.using(alias).exclude(evento__estado="anulado")
    duplicados = list(
        ocupados.values("turno_id").annotate(cantidad=Count("evento_id"))
        .filter(cantidad__gt=1).values_list("turno_id", flat=True)[:10]
    )
    if duplicados:
        raise RuntimeError(f"Hay varios eventos no Anulados en los turnos {duplicados}.")
    for evento in eventos.iterator():
        Evento.objects.using(alias).filter(pk=evento.pk).update(turno_id=evento.turno_asignado)


def crear_vinculos(apps, schema_editor):
    Evento = apps.get_model("reservas", "Evento")
    EventoTurno = apps.get_model("reservas", "EventoTurno")
    alias = schema_editor.connection.alias
    for evento in Evento.objects.using(alias).iterator():
        EventoTurno.objects.using(alias).create(evento_id=evento.pk, turno_id=evento.turno_id)


class Migration(migrations.Migration):
    dependencies = [("reservas", "0009_eventos_y_turnos")]

    operations = [
        migrations.AddField(
            model_name="evento",
            name="turno",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="eventos_directos",
                to="reservas.turno",
            ),
        ),
        migrations.RunPython(asignar_turnos, crear_vinculos),
        migrations.RemoveField(model_name="evento", name="turnos"),
        migrations.DeleteModel(name="EventoTurno"),
        migrations.AlterField(
            model_name="evento",
            name="turno",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="eventos",
                to="reservas.turno",
            ),
        ),
        migrations.AddConstraint(
            model_name="evento",
            constraint=models.UniqueConstraint(
                condition=~models.Q(estado="anulado"),
                fields=("turno",),
                name="evento_turno_ocupado_unico",
                violation_error_message="El turno ya está ocupado por otra actividad.",
            ),
        ),
    ]
