from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class SesionCaja(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = "abierta", "Abierta"
        CERRADA = "cerrada", "Cerrada"

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTA)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sesiones_caja")
    creado_en = models.DateTimeField(auto_now_add=True)
    efectivo_inicial = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    motivo_apertura = models.TextField(blank=True, default="")
    cerrada_en = models.DateTimeField(null=True, blank=True)
    efectivo_esperado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    efectivo_contado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    motivo_diferencia = models.TextField(blank=True, default="")

    class Meta:
        db_table = "sesiones_caja"
        ordering = ("-creado_en", "-pk")
        default_permissions = ()
        verbose_name = "sesión de caja"
        verbose_name_plural = "sesiones de caja"
        constraints = [
            models.UniqueConstraint(fields=("estado",), condition=models.Q(estado="abierta"), name="caja_sesion_abierta_unica"),
            models.CheckConstraint(condition=models.Q(efectivo_inicial__gte=0), name="caja_inicial_no_negativo"),
            models.CheckConstraint(condition=(
                models.Q(estado="abierta", cerrada_en__isnull=True, efectivo_esperado__isnull=True,
                         efectivo_contado__isnull=True, diferencia__isnull=True, motivo_diferencia="")
                | (models.Q(estado="cerrada", cerrada_en__isnull=False, cerrada_en__gte=models.F("creado_en"),
                            efectivo_esperado__isnull=False, efectivo_esperado__gte=0,
                            efectivo_contado__isnull=False, efectivo_contado__gte=0,
                            diferencia__isnull=False, diferencia=models.F("efectivo_contado") - models.F("efectivo_esperado"))
                   & (models.Q(diferencia=0, motivo_diferencia="") | (~models.Q(diferencia=0) & models.Q(motivo_diferencia__regex=r"\S"))))
            ), name="caja_cierre_coherente"),
        ]

    @property
    def numero(self):
        return f"C-{self.pk:06d}"

    def __str__(self):
        return self.numero


class MovimientoFondo(models.Model):
    class Clase(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"

    class Medio(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        TRANSFERENCIA = "transferencia", "Transferencia"
        TARJETA = "tarjeta", "Tarjeta"
        QR = "qr", "QR"

    class CategoriaIngreso(models.TextChoices):
        RESERVAS = "reservas", "Reservas"
        PLANES = "planes", "Planes"
        MEMBRESIAS = "membresias", "Membresías"
        OTROS = "otros", "Otros"

    class Estado(models.TextChoices):
        VIGENTE = "vigente", "Vigente"
        ANULADO = "anulado", "Anulado"

    operacion_id = models.UUIDField(unique=True)
    sesion = models.ForeignKey(SesionCaja, on_delete=models.PROTECT, related_name="movimientos")
    clase = models.CharField(max_length=10, choices=Clase.choices, default=Clase.INGRESO)
    concepto = models.TextField()
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    medio_pago = models.CharField(max_length=15, choices=Medio.choices)
    referencia = models.CharField(max_length=150, blank=True, default="")
    categoria_ingreso = models.CharField(max_length=20, choices=CategoriaIngreso.choices)
    plan_usuario = models.ForeignKey("membresias.PlanUsuario", on_delete=models.PROTECT, related_name="movimientos", null=True, blank=True)
    membresia_usuario = models.ForeignKey("membresias.MembresiaUsuario", on_delete=models.PROTECT, related_name="movimientos", null=True, blank=True)
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="movimientos", null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos_registrados")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    anulado_en = models.DateTimeField(null=True, blank=True)
    anulado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos_anulados", null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True, default="")

    class Meta:
        db_table = "movimientos_fondos"
        ordering = ("-creado_en", "-pk")
        default_permissions = ()
        verbose_name = "movimiento de fondos"
        verbose_name_plural = "movimientos de fondos"
        indexes = [models.Index(fields=("sesion", "id")), models.Index(fields=("creado_en",))]
        constraints = [
            models.CheckConstraint(condition=models.Q(clase="ingreso", monto__gt=0, concepto__regex=r"\S"), name="caja_ingreso_valido"),
            models.CheckConstraint(condition=(
                models.Q(medio_pago="efectivo")
                | models.Q(medio_pago__in=("transferencia", "tarjeta", "qr"), referencia__regex=r"\S")
            ), name="caja_medio_referencia_coherente"),
            models.CheckConstraint(condition=(
                models.Q(plan_usuario__isnull=True, membresia_usuario__isnull=True, reserva__isnull=True,
                         categoria_ingreso__in=("reservas", "planes", "membresias", "otros"))
                | models.Q(plan_usuario__isnull=False, membresia_usuario__isnull=True, reserva__isnull=True, categoria_ingreso="planes")
                | models.Q(plan_usuario__isnull=True, membresia_usuario__isnull=False, reserva__isnull=True, categoria_ingreso="membresias")
                | models.Q(plan_usuario__isnull=True, membresia_usuario__isnull=True, reserva__isnull=False, categoria_ingreso="reservas")
            ), name="caja_ingreso_origen_coherente"),
            models.CheckConstraint(condition=(
                models.Q(estado="vigente", anulado_en__isnull=True, anulado_por__isnull=True, motivo_anulacion="")
                | models.Q(estado="anulado", anulado_en__isnull=False, anulado_por__isnull=False, motivo_anulacion__regex=r"\S")
            ), name="caja_movimiento_anulacion_coherente"),
        ]

    @property
    def numero(self):
        return f"M-{self.pk:06d}"

    @property
    def origen(self):
        return self.plan_usuario or self.membresia_usuario or self.reserva

    def __str__(self):
        return self.numero
