from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.fechas import validar_inicio_evento
from common.models import RespuestaActividad


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
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="eventos")

    class Meta:
        db_table = "eventos"
        ordering = ("-creado_en", "-pk")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("turno",),
                condition=~models.Q(estado="anulado"),
                name="evento_turno_ocupado_unico",
                violation_error_message="El turno ya está ocupado por otra actividad.",
            ),
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
        ]
        verbose_name = "evento"
        verbose_name_plural = "eventos"

    def save(self, *args, **kwargs):
        if self._state.adding:
            validar_inicio_evento(self.turno.fecha, self.turno.hora_inicio)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Evento {self.pk}"


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
        validators=[MinValueValidator(Decimal("0.01"))], null=True, blank=True,
    )
    anulada_por_organizador = models.BooleanField(blank=True, null=True)
    membresia_usuario = models.ForeignKey("membresias.MembresiaUsuario", on_delete=models.PROTECT, related_name="reservas_aplicadas", null=True, blank=True)
    precio_invitado_aplicado = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))], null=True, blank=True)
    computa_hora_membresia = models.BooleanField(default=False)
    resultado_uso = models.CharField(max_length=15, choices=(("sin_registrar", "Sin registrar"), ("realizada", "Realizada"), ("no_realizada", "No realizada")), default="sin_registrar")
    resultado_registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    resultado_registrado_en = models.DateTimeField(null=True, blank=True)
    resultado_original = models.CharField(max_length=15, null=True, blank=True)
    resultado_corregido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    resultado_corregido_en = models.DateTimeField(null=True, blank=True)
    motivo_correccion_resultado = models.TextField(blank=True, default="")

    class Meta:
        db_table = "reservas"
        ordering = ("-evento__creado_en", "-pk")
        default_permissions = ("add", "view")
        constraints = [
            models.CheckConstraint(condition=(
                models.Q(membresia_usuario__isnull=True, precio_por_turno_aplicado__isnull=False,
                         precio_por_turno_aplicado__gte=Decimal("0.01"), precio_invitado_aplicado__isnull=True, computa_hora_membresia=False)
                | models.Q(membresia_usuario__isnull=False, precio_por_turno_aplicado__isnull=True,
                           precio_invitado_aplicado__isnull=False, precio_invitado_aplicado__gte=0)
            ), name="reserva_modalidad_coherente"),
            models.CheckConstraint(condition=(
                models.Q(resultado_uso="sin_registrar", resultado_registrado_por__isnull=True, resultado_registrado_en__isnull=True,
                         resultado_original__isnull=True, resultado_corregido_por__isnull=True, resultado_corregido_en__isnull=True,
                         motivo_correccion_resultado="")
                | (models.Q(membresia_usuario__isnull=False, resultado_uso__in=("realizada", "no_realizada"),
                            resultado_registrado_por__isnull=False, resultado_registrado_en__isnull=False)
                   & (models.Q(resultado_original__isnull=True, resultado_corregido_por__isnull=True,
                               resultado_corregido_en__isnull=True, motivo_correccion_resultado="")
                      | (models.Q(resultado_original__in=("realizada", "no_realizada"), resultado_original__isnull=False, resultado_corregido_por__isnull=False,
                                  resultado_corregido_en__isnull=False, motivo_correccion_resultado__regex=r"\S")
                         & ~models.Q(resultado_original=models.F("resultado_uso")))))
            ), name="reserva_resultado_coherente"),
        ]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"

    def __str__(self):
        return f"Reserva {self.pk}"

    @property
    def numero(self):
        return f"R-{self.pk:06d}" if self.pk is not None else ""


    @property
    def resultado_original_texto(self):
        return dict(self._meta.get_field("resultado_uso").choices).get(self.resultado_original, "")

    @property
    def es_con_membresia(self):
        return self.membresia_usuario_id is not None

    @property
    def total(self):
        if not self.es_con_membresia:
            return self.precio_por_turno_aplicado
        return self.precio_invitado_aplicado * sum(
            invitado.estado == "vigente" and invitado.respuesta != "negativa" and invitado.genera_adicional
            for invitado in self.invitados.all()
        )


class ReservaInvitado(RespuestaActividad):
    pk = models.CompositePrimaryKey("reserva_id", "usuario_id")
    reserva = models.ForeignKey(Reserva, on_delete=models.PROTECT, related_name="invitados")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invitaciones_reserva")
    membresia_usuario = models.ForeignKey("membresias.MembresiaUsuario", on_delete=models.PROTECT, related_name="invitaciones_aplicadas", null=True, blank=True)
    condicion_aplicada = models.CharField(max_length=20, choices=(
        ("socio", "Socio con beneficio"), ("no_socio", "No socio"),
        ("cupo_agotado", "Socio con cupo de invitado agotado"), ("reserva_normal", "Reserva normal"),
    ))
    estado = models.CharField(max_length=10, choices=(("vigente", "Vigente"), ("retirado", "Retirado")), default="vigente")
    retirado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    retirado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reservas_invitados"
        ordering = ("creado_en", "usuario_id")
        default_permissions = ()
        constraints = [
            *RespuestaActividad.Meta.constraints,
            models.CheckConstraint(condition=(
                models.Q(estado="vigente", retirado_por__isnull=True, retirado_en__isnull=True)
                | models.Q(estado="retirado", retirado_por__isnull=False, retirado_en__isnull=False)
            ), name="invitado_retiro_coherente"),
            models.CheckConstraint(condition=(
                models.Q(condicion_aplicada__in=("socio", "cupo_agotado"), membresia_usuario__isnull=False)
                | models.Q(condicion_aplicada__in=("no_socio", "reserva_normal"), membresia_usuario__isnull=True)
            ), name="invitado_condicion_coherente"),
        ]
        verbose_name = "invitación de reserva"
        verbose_name_plural = "invitaciones de reservas"

    def __str__(self):
        return f"{self.reserva.numero} · {self.usuario}"

    @property
    def genera_adicional(self):
        return self.condicion_aplicada in ("no_socio", "cupo_agotado")

    @property
    def respuesta_inicial_texto(self):
        return {"afirmativa": "Aceptada", "negativa": "Rechazada"}.get(self.respuesta_inicial, "")

    def get_respuesta_display(self):
        return {"pendiente": "Pendiente", "afirmativa": "Aceptada", "negativa": "Rechazada"}[self.respuesta]
