from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("reservas", "0004_participacion_y_membresias"), ("auditoria", "0003_triggers_auditoria")]
    operations = [migrations.RunSQL(
        sql="CREATE TRIGGER auditar_reservas_invitados AFTER UPDATE OR DELETE ON reservas_invitados FOR EACH ROW EXECUTE FUNCTION registrar_auditoria('reserva_id', 'usuario_id');",
        reverse_sql="DROP TRIGGER auditar_reservas_invitados ON reservas_invitados;",
    )]
