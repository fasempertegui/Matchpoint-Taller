from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class PrecioReserva(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    sede = models.ForeignKey(
        "instalaciones.Sede",
        on_delete=models.PROTECT,
        related_name="precios_reservas",
    )
    importe = models.DecimalField(
        "Precio por turno (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "precios_reservas_cancha"
        ordering = ("sede__nombre", "-creado_en", "-pk")
        default_permissions = ("add", "change", "view")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(importe__gte=Decimal("0.01")),
                name="precio_reserva_importe_positivo",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")),
                name="precio_reserva_estado_valido",
            ),
            models.UniqueConstraint(
                fields=("sede",),
                condition=models.Q(estado="activo"),
                name="precio_reserva_sede_activo_unico",
                violation_error_message="Ya existe un precio activo para esta sede.",
            ),
        ]
        verbose_name = "precio de reserva"
        verbose_name_plural = "precios de reservas"

    def __str__(self):
        return f"Precio por turno ({self.sede.nombre})"


class Turno(models.Model):
    id = models.BigAutoField(primary_key=True)
    cancha = models.ForeignKey(
        "instalaciones.Cancha",
        on_delete=models.PROTECT,
        related_name="turnos",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
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
                condition=models.Q(hora_inicio__in=tuple(time(hora) for hora in range(23)),hora_fin=models.F("hora_inicio") + timedelta(hours=1),),
                name="turno_horario_valido",
                violation_error_message=("El turno debe durar una hora, comenzar en punto y terminar dentro de la misma fecha."),),
        ]
        verbose_name = "turno"
        verbose_name_plural = "turnos"

    def __str__(self):
        return f"{self.cancha} - {self.fecha:%d/%m/%Y} {self.hora_inicio:%H:%M}"


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
    precio_reserva = models.ForeignKey(
        PrecioReserva,
        on_delete=models.PROTECT,
        related_name="reservas",
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
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas_finalizadas",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "reservas"
        ordering = ("-creado_en", "-pk")
        default_permissions = ("add", "view")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        estado="programada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=True,
                        finalizado_por__isnull=True,
                    )
                    | models.Q(
                        estado="anulada",
                        anulado_en__isnull=False,
                        anulado_por__isnull=False,
                        motivo_anulacion__regex=r"\S",
                        finalizado_en__isnull=True,
                        finalizado_por__isnull=True,
                    )
                    | models.Q(
                        estado="finalizada",
                        anulado_en__isnull=True,
                        anulado_por__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=False,
                        finalizado_por__isnull=False,
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
