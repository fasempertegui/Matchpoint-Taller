from django.conf import settings
from django.db import models
from django.utils import timezone


class LogAuditoria(models.Model):
    class Accion(models.TextChoices):
        MODIFICACION = "modificacion", "Modificación"
        ANULACION = "anulacion", "Anulación"
        ELIMINACION = "eliminacion", "Eliminación"
        CAMBIO_CONTRASENA = "cambio_contrasena", "Cambio de contraseña"
        RESTABLECIMIENTO_CONTRASENA = "restablecimiento_contrasena", "Restablecimiento de contraseña"
        ACTUALIZACION_HASH = "actualizacion_hash", "Actualización de hash"

    class Origen(models.TextChoices):
        APLICACION = "aplicacion", "Aplicación"
        TAREA = "tarea", "Tarea automática"
        SQL = "sql", "SQL"

    id = models.BigAutoField(primary_key=True)
    operacion_id = models.UUIDField(db_index=True)
    tabla = models.CharField(max_length=63)
    clave_registro = models.JSONField()
    accion = models.CharField(max_length=32, choices=Accion.choices)
    valores_anteriores = models.JSONField()
    valores_actuales = models.JSONField()
    realizado_en = models.DateTimeField(default=timezone.now, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_auditoria",
        null=True,
        blank=True,
    )
    usuario_bd = models.CharField(max_length=63)
    origen = models.CharField(max_length=10, choices=Origen.choices)

    class Meta:
        db_table = "log_auditoria"
        ordering = ("-realizado_en", "-pk")
        default_permissions = ()
        indexes = [
            models.Index(fields=("tabla", "-realizado_en"), name="auditoria_tabla_fecha_idx"),
            models.Index(fields=("usuario", "-realizado_en"), name="auditoria_usuario_fecha_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(accion__in=(
                    "modificacion", "anulacion", "eliminacion", "cambio_contrasena",
                    "restablecimiento_contrasena", "actualizacion_hash",
                )),
                name="auditoria_accion_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(origen__in=("aplicacion", "tarea", "sql")),
                name="auditoria_origen_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(origen="aplicacion", usuario__isnull=False)
                    | models.Q(origen__in=("tarea", "sql"), usuario__isnull=True)
                ),
                name="auditoria_actor_y_origen_validos",
            ),
        ]
