import common.fechas
from django.db import migrations, models


def verificar_fechas_nacimiento(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    sin_fecha = list(
        Usuario.objects.using(schema_editor.connection.alias)
        .filter(fecha_nacimiento__isnull=True)
        .values_list("id", flat=True)
    )
    if sin_fecha:
        raise ValueError(
            "Hay usuarios sin fecha de nacimiento (IDs: "
            + ", ".join(map(str, sin_fecha))
            + "). Cargá sus fechas antes de aplicar esta migración."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0002_cargar_roles"),
    ]

    operations = [
        migrations.RunPython(
            verificar_fechas_nacimiento,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="usuario",
            name="fecha_nacimiento",
            field=models.DateField(validators=[common.fechas.validar_fecha_nacimiento]),
        ),
    ]
