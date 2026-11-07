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
