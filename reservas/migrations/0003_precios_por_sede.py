import django.db.models.deletion
from django.db import migrations, models


def copiar_tarifas_por_sede(apps, schema_editor):
    Sede = apps.get_model("instalaciones", "Sede")
    PrecioReserva = apps.get_model("reservas", "PrecioReserva")
    base_datos = schema_editor.connection.alias
    precios = PrecioReserva.objects.using(base_datos)
    tarifas = list(
        precios.values(
            "duracion_horas",
            "precio_vigente",
            "estado",
            "creado_en",
            "actualizado_en",
        )
    )
    if not tarifas:
        return

    sedes = list(Sede.objects.using(base_datos).order_by("pk").values_list("pk", flat=True))
    if not sedes:
        raise RuntimeError("Se necesita al menos una sede para asignar las tarifas existentes.")

    precios.update(sede_id=sedes[0])
    for sede_id in sedes[1:]:
        for tarifa in tarifas:
            copia = precios.create(
                sede_id=sede_id,
                duracion_horas=tarifa["duracion_horas"],
                precio_vigente=tarifa["precio_vigente"],
                estado=tarifa["estado"],
            )
            # La copia conserva las fechas del catálogo, sin aplicar las fechas automáticas del alta.
            precios.filter(pk=copia.pk).update(
                creado_en=tarifa["creado_en"],
                actualizado_en=tarifa["actualizado_en"],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("instalaciones", "0002_sede_horario"),
        ("reservas", "0002_limitar_duracion_precio"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="precioreserva",
            name="precio_reserva_duracion_activa_unica",
        ),
        migrations.AddField(
            model_name="precioreserva",
            name="sede",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="precios_reservas",
                to="instalaciones.sede",
            ),
        ),
        migrations.RunPython(copiar_tarifas_por_sede),
        migrations.AlterField(
            model_name="precioreserva",
            name="sede",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="precios_reservas",
                to="instalaciones.sede",
            ),
        ),
        migrations.AlterModelOptions(
            name="precioreserva",
            options={
                "default_permissions": ("add", "change", "view"),
                "ordering": ("sede__nombre", "duracion_horas", "-creado_en"),
                "verbose_name": "precio de reserva",
                "verbose_name_plural": "precios de reservas",
            },
        ),
        migrations.AddConstraint(
            model_name="precioreserva",
            constraint=models.UniqueConstraint(
                condition=models.Q(estado="activo"),
                fields=("sede", "duracion_horas"),
                name="precio_reserva_sede_duracion_activa_unica",
                violation_error_message="Ya existe una tarifa activa para esa duración en esta sede.",
            ),
        ),
    ]
