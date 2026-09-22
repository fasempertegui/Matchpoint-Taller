from django.db import models
from django.db.models.functions import Lower


class Sede(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=250)
    observaciones = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVA,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sedes"
        ordering = ("nombre",)
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="sede_nombre_unico_sin_mayusculas",
                violation_error_message="Ya existe una sede con ese nombre.",
            ),
        ]
        verbose_name = "sede"
        verbose_name_plural = "sedes"

    def __str__(self):
        return self.nombre


class Cancha(models.Model):
    class Superficie(models.TextChoices):
        CEMENTO = "cemento", "Cemento"
        POLVO_LADRILLO = "polvo_ladrillo", "Polvo de ladrillo"

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="canchas")
    nombre = models.CharField(max_length=120)
    superficie = models.CharField(max_length=30, choices=Superficie.choices)
    observaciones = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVA,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "canchas"
        ordering = ("sede__nombre", "nombre")
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                "sede",
                name="cancha_nombre_unico_por_sede_sin_mayusculas",
                violation_error_message="Ya existe una cancha con ese nombre en esta sede.",
            ),
        ]
        verbose_name = "cancha"
        verbose_name_plural = "canchas"

    def __str__(self):
        return f"{self.nombre} ({self.sede.nombre})"
