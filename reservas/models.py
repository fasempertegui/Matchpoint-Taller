from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Turno(models.Model):
    id = models.BigAutoField(primary_key=True)
    cancha = models.ForeignKey(
        "instalaciones.Cancha",
        on_delete=models.PROTECT,
        related_name="turnos",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "turnos"
        ordering = ("fecha", "hora_inicio", "cancha_id")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("cancha", "fecha", "hora_inicio"),
                name="turno_cancha_fecha_inicio_unico",
                violation_error_message="Ya existe un turno para esa cancha, fecha y hora.",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_inicio__in=tuple(time(hora) for hora in range(23))),
                name="turno_horario_valido",
                violation_error_message="El turno debe comenzar en punto entre las 00:00 y las 22:00.",
            ),
        ]
        verbose_name = "turno"
        verbose_name_plural = "turnos"

    def __str__(self):
        return f"{self.cancha} - {self.fecha:%d/%m/%Y} {self.hora_inicio:%H:%M}"

    @property
    def hora_fin(self):
        return (datetime.combine(self.fecha, self.hora_inicio) + timedelta(hours=1)).time()


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        FINALIZADA = "finalizada", "Finalizada"
        ANULADA = "anulada", "Anulada"

    id = models.BigAutoField(primary_key=True)
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas_registradas",
    )
    precio_por_turno_aplicado = models.DecimalField(
        "Precio por turno aplicado (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PROGRAMADA,
    )
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    anulado_en = models.DateTimeField(blank=True, null=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas_anuladas",
        blank=True,
        null=True,
    )
    motivo_anulacion = models.TextField(blank=True)
    finalizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "reservas"
        ordering = ("-creado_en", "-pk")
        default_permissions = ("add", "view")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(precio_por_turno_aplicado__gte=Decimal("0.01")),
                name="reserva_precio_por_turno_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        estado="programada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="anulada",
                        anulado_en__isnull=False,
                        anulado_por__isnull=False,
                        motivo_anulacion__regex=r"\S",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="finalizada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=False,
                    )
                ),
                name="reserva_estado_y_auditoria_validos",
                violation_error_message=("Los datos de anulación y finalización deben corresponder al estado de la reserva. La anulación requiere un motivo."),
            ),
        ]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"

    def __str__(self):
        return f"Reserva {self.pk}"

    @property
    def numero(self):
        return f"R-{self.pk:06d}" if self.pk is not None else ""


class ReservaTurno(models.Model):
    id = models.BigAutoField(primary_key=True)
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.PROTECT,
        related_name="detalles",
    )
    turno = models.ForeignKey(
        Turno,
        on_delete=models.PROTECT,
        related_name="reservas_turnos",
    )

    class Meta:
        db_table = "reservas_turnos"
        ordering = ("turno__fecha", "turno__hora_inicio", "pk")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("reserva", "turno"),
                name="reserva_turno_unico",
                violation_error_message="El turno ya está incluido en esta reserva.",
            ),
        ]
        verbose_name = "turno de reserva"
        verbose_name_plural = "turnos de reserva"

    def __str__(self):
        return f"{self.reserva} - {self.turno}"
