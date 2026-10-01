from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Sede(models.Model):

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    id = models.BigAutoField(primary_key=True)
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

    id = models.BigAutoField(primary_key=True)
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


class SedeHorario(models.Model):
    class DiaSemana(models.IntegerChoices):
        LUNES = 1, "Lunes"
        MARTES = 2, "Martes"
        MIERCOLES = 3, "Miércoles"
        JUEVES = 4, "Jueves"
        VIERNES = 5, "Viernes"
        SABADO = 6, "Sábado"
        DOMINGO = 7, "Domingo"

    pk = models.CompositePrimaryKey("sede_id", "dia_semana")
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="horarios")
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    hora_inicio_1 = models.TimeField("Inicio de la primera franja")
    hora_fin_1 = models.TimeField("Fin de la primera franja")
    hora_inicio_2 = models.TimeField("Inicio de la segunda franja", blank=True, null=True)
    hora_fin_2 = models.TimeField("Fin de la segunda franja", blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sedes_horarios"
        ordering = ("dia_semana",)
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(dia_semana__gte=1, dia_semana__lte=7),
                name="sede_horario_dia_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_fin_1__gt=models.F("hora_inicio_1")),
                name="sede_horario_primera_franja_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True, hora_fin_2__isnull=True)
                    | models.Q(hora_inicio_2__isnull=False, hora_fin_2__isnull=False)
                ),
                name="sede_horario_segunda_franja_completa",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True)
                    | models.Q(hora_fin_2__gt=models.F("hora_inicio_2"))
                ),
                name="sede_horario_segunda_franja_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True)
                    | models.Q(hora_inicio_2__gte=models.F("hora_fin_1"))
                ),
                name="sede_horario_franjas_sin_superposicion",
            ),
        ]
        verbose_name = "horario de sede"
        verbose_name_plural = "horarios de sede"

    def __str__(self):
        return f"{self.sede} - {self.get_dia_semana_display()}"

    def clean(self):
        super().clean()
        horas = (
            self.hora_inicio_1,
            self.hora_fin_1,
            self.hora_inicio_2,
            self.hora_fin_2,
        )
        if all(hora is None for hora in horas):
            return

        errores = {}
        if self.hora_inicio_1 is None:
            errores["hora_inicio_1"] = "Indicá el inicio de la primera franja."
        if self.hora_fin_1 is None:
            errores["hora_fin_1"] = "Indicá el fin de la primera franja."
        if (
            self.hora_inicio_1 is not None
            and self.hora_fin_1 is not None
            and self.hora_fin_1 <= self.hora_inicio_1
        ):
            errores["hora_fin_1"] = "El fin debe ser posterior al inicio."

        if self.hora_inicio_2 is None and self.hora_fin_2 is not None:
            errores["hora_inicio_2"] = "Indicá el inicio de la segunda franja."
        if self.hora_fin_2 is None and self.hora_inicio_2 is not None:
            errores["hora_fin_2"] = "Indicá el fin de la segunda franja."
        if self.hora_inicio_2 is not None and self.hora_fin_2 is not None:
            if self.hora_fin_2 <= self.hora_inicio_2:
                errores["hora_fin_2"] = "El fin debe ser posterior al inicio."
            if self.hora_fin_1 is not None and self.hora_inicio_2 < self.hora_fin_1:
                errores["hora_inicio_2"] = (
                    "La segunda franja debe comenzar al terminar la primera o después."
                )

        if errores:
            raise ValidationError(errores)
