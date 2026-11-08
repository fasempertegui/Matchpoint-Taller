from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0005_remove_movimientofondo_caja_ingreso_valido_and_more'),
        ('membresias', '0012_auditoria_contrataciones_membresia'),
        ('reservas', '0007_reserva_reprogramada_desde_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='movimientofondo',
            name='caja_movimiento_campos_coherentes',
        ),
        migrations.AddConstraint(
            model_name='movimientofondo',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('categoria_egreso', ''), ('clase', 'ingreso'), ('destinatario', ''), models.Q(models.Q(('categoria_ingreso', 'otros'), ('membresia_usuario__isnull', True), ('plan_usuario__isnull', True), ('reserva__isnull', True)), models.Q(('categoria_ingreso', 'planes'), ('membresia_usuario__isnull', True), ('plan_usuario__isnull', False), ('reserva__isnull', True)), models.Q(('categoria_ingreso', 'membresias'), ('membresia_usuario__isnull', False), ('plan_usuario__isnull', True), ('reserva__isnull', True)), models.Q(('categoria_ingreso', 'reservas'), ('membresia_usuario__isnull', True), ('plan_usuario__isnull', True), ('reserva__isnull', False)), _connector='OR')), models.Q(('categoria_ingreso', ''), ('membresia_usuario__isnull', True), ('plan_usuario__isnull', True), ('reserva__isnull', True), models.Q(models.Q(('categoria_egreso__in', ('alquiler', 'servicios', 'profesores', 'insumos', 'mantenimiento', 'publicidad', 'otros', 'devoluciones')), ('clase', 'egreso')), models.Q(('categoria_egreso', ''), ('clase__in', ('aporte', 'retiro')), ('destinatario', ''), ('medio_pago', 'efectivo')), _connector='OR')), _connector='OR'), name='caja_movimiento_campos_coherentes'),
        ),
    ]
