from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Plan(models.Model):
    class Modalidad(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        GRUPAL = "grupal", "Grupal"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField("Descripción", blank=True, default="")
    modalidad = models.CharField(max_length=15, choices=Modalidad.choices)
    frecuencia_semanal = models.PositiveSmallIntegerField(
        "Encuentros por semana", choices=tuple((numero, str(numero)) for numero in range(1, 8)),
    )
    cantidad_clases_por_encuentro = models.PositiveSmallIntegerField(
        "Duración de cada encuentro", choices=((1, "1 hora"), (2, "2 horas")),
    )
    precio_vigente = models.DecimalField(
        "Precio mensual (ARS)", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planes"
        ordering = ("nombre", "pk")
        default_permissions = ()
        verbose_name = "plan"
        verbose_name_plural = "planes"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"), condition=models.Q(estado="activo"),
                name="plan_nombre_activo_unico",
                violation_error_message="Ya existe un plan activo con ese nombre.",
            ),
            models.CheckConstraint(condition=models.Q(nombre__regex=r"\S"), name="plan_nombre_no_vacio"),
            models.CheckConstraint(
                condition=models.Q(modalidad__in=("individual", "grupal")), name="plan_modalidad_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(frecuencia_semanal__gte=1, frecuencia_semanal__lte=7),
                name="plan_frecuencia_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_clases_por_encuentro__in=(1, 2)), name="plan_duracion_valida",
            ),
            models.CheckConstraint(condition=models.Q(precio_vigente__gte=0), name="plan_precio_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")), name="plan_estado_valido",
            ),
        ]

    def __str__(self):
        return self.nombre
