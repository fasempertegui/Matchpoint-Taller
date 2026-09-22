from django.db import migrations


def cargar_roles(apps, schema_editor):
    Rol = apps.get_model("usuarios", "Rol")
    roles = (
        ("administrador", "Administrador"),
        ("profesor", "Profesor"),
        ("alumno", "Alumno"),
        ("reservas", "Reservas"),
        ("publico", "Público"),
    )

    for codigo, nombre in roles:
        Rol.objects.using(schema_editor.connection.alias).get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(cargar_roles, migrations.RunPython.noop),
    ]
