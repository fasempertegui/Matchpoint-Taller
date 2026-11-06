from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("reservas", "0002_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="evento",
            name="evento_bloqueo_no_finalizado",
        ),
    ]
