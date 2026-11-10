from importlib import import_module

from django.db import migrations


FUNCION = import_module("auditoria.migrations.0003_triggers_auditoria").CREAR_FUNCIONES.split(
    "\nCREATE FUNCTION proteger_log_auditoria"
)[0].replace("CREATE FUNCTION registrar_auditoria", "CREATE OR REPLACE FUNCTION registrar_auditoria")


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0005_actores_cuentas_iniciales")]

    operations = [migrations.RunSQL(
        FUNCION.replace("registro_anterior - 'password'", "registro_anterior - 'password' - 'verificacion_solicitada_en'"),
        reverse_sql=FUNCION,
    )]
