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


class Evento(models.Model):
    class Tipo(models.TextChoices):
        RESERVA = "reserva", "Reserva"
        CLASE = "clase", "Clase"
        BLOQUEO = "bloqueo", "Bloqueo"

    class Estado(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        ANULADO = "anulado", "Anulado"
        FINALIZADO = "finalizado", "Finalizado"

    id = models.BigAutoField(primary_key=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PROGRAMADO)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_registrados",
    )
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_anulados",
        blank=True,
        null=True,
    )
    anulado_en = models.DateTimeField(blank=True, null=True)
    motivo_anulacion = models.TextField(blank=True)
    finalizado_en = models.DateTimeField(blank=True, null=True)
    turnos = models.ManyToManyField(Turno, through="EventoTurno", related_name="eventos")

    class Meta:
        db_table = "eventos"
        ordering = ("-creado_en", "-pk")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tipo__in=("reserva", "clase", "bloqueo")),
                name="evento_tipo_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        estado="programado",
                        anulado_por__isnull=True,
                        anulado_en__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="anulado",
                        anulado_por__isnull=False,
                        anulado_en__isnull=False,
                        motivo_anulacion__regex=r"\S",
                        finalizado_en__isnull=True,
                    )
                    | models.Q(
                        estado="finalizado",
                        anulado_por__isnull=True,
                        anulado_en__isnull=True,
                        motivo_anulacion="",
                        finalizado_en__isnull=False,
                    )
                ),
                name="evento_estado_y_auditoria_validos",
                violation_error_message="Los datos de anulación y finalización deben corresponder al estado del evento.",
            ),
            models.CheckConstraint(
                condition=~models.Q(tipo="bloqueo", estado="finalizado"),
                name="evento_bloqueo_no_finalizado",
            ),
        ]
        verbose_name = "evento"
        verbose_name_plural = "eventos"

    def __str__(self):
        return f"Evento {self.pk}"


class EventoTurno(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name="detalles")
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="vinculos_eventos")

    class Meta:
        db_table = "eventos_turnos"
        ordering = ("turno__fecha", "turno__hora_inicio", "pk")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("evento", "turno"),
                name="evento_turno_unico",
                violation_error_message="El turno ya está incluido en este evento.",
            ),
        ]
        verbose_name = "turno de evento"
        verbose_name_plural = "turnos de eventos"

    def __str__(self):
        return f"{self.evento} - {self.turno}"


class Reserva(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento = models.OneToOneField(
        Evento,
        on_delete=models.PROTECT,
        related_name="reserva",
        limit_choices_to={"tipo": Evento.Tipo.RESERVA},
    )
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    precio_por_turno_aplicado = models.DecimalField(
        "Precio por turno aplicado (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    anulada_por_organizador = models.BooleanField(blank=True, null=True)

    class Meta:
        db_table = "reservas"
        ordering = ("-evento__creado_en", "-pk")
        default_permissions = ("add", "view")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(precio_por_turno_aplicado__gte=Decimal("0.01")),
                name="reserva_precio_por_turno_positivo",
            ),
        ]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"

    def __str__(self):
        return f"Reserva {self.pk}"

    @property
    def numero(self):
        return f"R-{self.pk:06d}" if self.pk is not None else ""
