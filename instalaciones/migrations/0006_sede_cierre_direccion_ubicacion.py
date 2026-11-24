from decimal import Decimal

from django.db import migrations, models

from instalaciones.direcciones import LOCALIDADES_SALTA
from instalaciones.ubicacion import punto_en_localidad


def verificar_sedes_completas(apps, schema_editor):
    Sede = apps.get_model("instalaciones", "Sede")
    pendientes = []
    for sede in Sede.objects.order_by("id"):
        faltantes = []
        if sede.localidad_codigo not in LOCALIDADES_SALTA:
            faltantes.append("localidad habilitada")
        if not (sede.calle or "").strip():
            faltantes.append("calle")
        if not (sede.altura or "").strip():
            faltantes.append("altura")
        if sede.latitud is None or sede.longitud is None:
            faltantes.append("coordenadas de entrada")
        elif sede.localidad_codigo in LOCALIDADES_SALTA and not punto_en_localidad(
            sede.localidad_codigo,
            sede.latitud,
            sede.longitud,
        ):
            faltantes.append("pin dentro de la localidad seleccionada")
        if faltantes:
            pendientes.append(
                f"Sede #{sede.id} ({sede.nombre}, {sede.estado}): falta {', '.join(faltantes)}"
            )
    if pendientes:
        detalle = "\n".join(f"- {item}" for item in pendientes)
        raise RuntimeError(
            "No se puede cerrar la migración de sedes porque existen registros pendientes:\n"
            f"{detalle}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("instalaciones", "0005_sede_ubicacion"),
    ]

    operations = [
        migrations.RunPython(verificar_sedes_completas, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="sede",
            name="sede_localidad_codigo_habilitado",
        ),
        migrations.RemoveConstraint(
            model_name="sede",
            name="sede_direccion_estructurada_coherente",
        ),
        migrations.RemoveConstraint(
            model_name="sede",
            name="sede_coordenadas_completas",
        ),
        migrations.RemoveConstraint(
            model_name="sede",
            name="sede_latitud_rango",
        ),
        migrations.RemoveConstraint(
            model_name="sede",
            name="sede_longitud_rango",
        ),
        migrations.RemoveField(
            model_name="sede",
            name="direccion",
        ),
        migrations.AlterField(
            model_name="sede",
            name="altura",
            field=models.CharField(max_length=20, verbose_name="Altura"),
        ),
        migrations.AlterField(
            model_name="sede",
            name="calle",
            field=models.CharField(max_length=150, verbose_name="Calle"),
        ),
        migrations.AlterField(
            model_name="sede",
            name="latitud",
            field=models.DecimalField(decimal_places=6, max_digits=9, verbose_name="Latitud"),
        ),
        migrations.AlterField(
            model_name="sede",
            name="localidad_codigo",
            field=models.CharField(
                choices=[
                    ("66028050", "Ciudad de Salta"),
                    ("66077020", "Vaqueros"),
                    ("66028060", "San Lorenzo"),
                    ("66035010", "Cerrillos"),
                ],
                max_length=8,
                verbose_name="Localidad",
            ),
        ),
        migrations.AlterField(
            model_name="sede",
            name="longitud",
            field=models.DecimalField(decimal_places=6, max_digits=9, verbose_name="Longitud"),
        ),
        migrations.AddConstraint(
            model_name="sede",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("localidad_codigo__in", ("66028050", "66077020", "66028060", "66035010"))
                ),
                name="sede_localidad_codigo_habilitado",
                violation_error_message="La localidad seleccionada no está habilitada.",
            ),
        ),
        migrations.AddConstraint(
            model_name="sede",
            constraint=models.CheckConstraint(
                condition=models.Q(("calle__regex", "\\S"), ("altura__regex", "\\S")),
                name="sede_direccion_estructurada_completa",
                violation_error_message="La dirección estructurada requiere localidad, calle y altura.",
            ),
        ),
        migrations.AddConstraint(
            model_name="sede",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("latitud__gte", Decimal("-90.000000")),
                    ("latitud__lte", Decimal("90.000000")),
                ),
                name="sede_latitud_rango",
                violation_error_message="La latitud debe estar entre -90 y 90.",
            ),
        ),
        migrations.AddConstraint(
            model_name="sede",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("longitud__gte", Decimal("-180.000000")),
                    ("longitud__lte", Decimal("180.000000")),
                ),
                name="sede_longitud_rango",
                violation_error_message="La longitud debe estar entre -180 y 180.",
            ),
        ),
    ]
