from datetime import time

from django.conf import settings
from django.db import models


class Feriado(models.Model):
    id = models.BigAutoField(primary_key=True)
    fecha = models.DateField(unique=True)
    descripcion = models.CharField(max_length=150)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feriados"
        ordering = ("fecha",)
        default_permissions = ()
        verbose_name = "feriado"
        verbose_name_plural = "feriados"

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} - {self.descripcion}"


class TurnoPlanilla(models.Model):
    class DiaSemana(models.IntegerChoices):
        LUNES = 1, "Lunes"
        MARTES = 2, "Martes"
        MIERCOLES = 3, "Miércoles"
        JUEVES = 4, "Jueves"
        VIERNES = 5, "Viernes"
        SABADO = 6, "Sábado"
        DOMINGO = 7, "Domingo"

    class Modalidad(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        GRUPAL = "grupal", "Grupal"

    id = models.BigAutoField(primary_key=True)
    cancha = models.ForeignKey(
        "instalaciones.Cancha",
        on_delete=models.PROTECT,
        related_name="turnos_planilla",
    )
    dia_semana = models.SmallIntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    modalidad = models.CharField(
        max_length=15,
        choices=Modalidad.choices,
        blank=True,
        null=True,
    )
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "turnos_planilla"
        ordering = ("cancha_id", "dia_semana", "hora_inicio")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("cancha", "dia_semana", "hora_inicio"),
                name="turno_planilla_cancha_dia_hora_unico",
                violation_error_message="Ya existe un turno de planilla para esa cancha, día y hora.",
            ),
            models.CheckConstraint(
                condition=models.Q(dia_semana__gte=1, dia_semana__lte=7),
                name="turno_planilla_dia_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_inicio__in=tuple(time(hora) for hora in range(23))),
                name="turno_planilla_horario_valido",
                violation_error_message="El turno debe comenzar en punto entre las 00:00 y las 22:00.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(modalidad__isnull=True)
                    | models.Q(modalidad__in=("individual", "grupal"))
                ),
                name="turno_planilla_modalidad_valida",
            ),
        ]
        verbose_name = "turno de planilla"
        verbose_name_plural = "turnos de planilla"

    def __str__(self):
        return f"{self.cancha} - {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}"


class TurnoPlanillaProfesor(models.Model):
    pk = models.CompositePrimaryKey("turno_planilla_id", "profesor_id")
    turno_planilla = models.ForeignKey(
        TurnoPlanilla,
        on_delete=models.CASCADE,
        related_name="profesores",
    )
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turnos_planilla_como_profesor",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "turnos_planilla_profesores"
        ordering = ("turno_planilla_id", "profesor_id")
        default_permissions = ()
        verbose_name = "profesor de turno de planilla"
        verbose_name_plural = "profesores de turnos de planilla"

    def __str__(self):
        return f"{self.turno_planilla} - {self.profesor}"


class TurnoPlanillaAlumno(models.Model):
    pk = models.CompositePrimaryKey("turno_planilla_id", "usuario_id")
    turno_planilla = models.ForeignKey(
        TurnoPlanilla,
        on_delete=models.CASCADE,
        related_name="alumnos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turnos_planilla_como_participante",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "turnos_planilla_alumnos"
        ordering = ("turno_planilla_id", "usuario_id")
        default_permissions = ()
        verbose_name = "participante de turno de planilla"
        verbose_name_plural = "participantes de turnos de planilla"

    def __str__(self):
        return f"{self.turno_planilla} - {self.usuario}"


class Clase(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento = models.OneToOneField(
        "reservas.Evento",
        on_delete=models.PROTECT,
        related_name="clase",
        limit_choices_to={"tipo": "clase"},
    )
    turno_planilla = models.ForeignKey(
        TurnoPlanilla,
        on_delete=models.SET_NULL,
        related_name="clases",
        blank=True,
        null=True,
    )
    es_generada = models.BooleanField(default=False)
    modalidad = models.CharField(
        max_length=15,
        choices=TurnoPlanilla.Modalidad.choices,
        blank=True,
        null=True,
    )
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clases_finalizadas",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "clases"
        ordering = ("-evento__turno__fecha", "-evento__turno__hora_inicio", "-pk")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(modalidad__isnull=True)
                    | models.Q(modalidad__in=("individual", "grupal"))
                ),
                name="clase_modalidad_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(es_generada=True) | models.Q(turno_planilla__isnull=True),
                name="clase_origen_planilla_valido",
                violation_error_message="Una clase manual no puede tener un turno de planilla de origen.",
            ),
        ]
        verbose_name = "clase"
        verbose_name_plural = "clases"

    def __str__(self):
        return f"Clase {self.pk}"


class ClaseProfesor(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    pk = models.CompositePrimaryKey("clase_id", "profesor_id")
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="profesores")
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clases_como_profesor",
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clases_profesores"
        ordering = ("clase_id", "profesor_id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")),
                name="clase_profesor_estado_valido",
            ),
        ]
        verbose_name = "profesor de clase"
        verbose_name_plural = "profesores de clases"

    def __str__(self):
        return f"{self.clase} - {self.profesor}"


class ClaseAlumno(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    pk = models.CompositePrimaryKey("clase_id", "usuario_id")
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="alumnos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clases_como_participante",
    )
    observaciones = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    recordatorio_enviado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clases_alumnos"
        ordering = ("clase_id", "usuario_id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")),
                name="clase_alumno_estado_valido",
            ),
        ]
        verbose_name = "participante de clase"
        verbose_name_plural = "participantes de clases"

    def __str__(self):
        return f"{self.clase} - {self.usuario}"


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        SIN_REGISTRAR = "sin_registrar", "Sin registrar"

    pk = models.CompositePrimaryKey("clase_id", "usuario_id")
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="asistencias")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asistencias",
    )
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.SIN_REGISTRAR)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asistencias_registradas",
        blank=True,
        null=True,
    )
    observaciones = models.TextField(blank=True, null=True)
    registrada_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asistencias"
        ordering = ("clase_id", "usuario_id")
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(estado="sin_registrar")
                    | models.Q(
                        estado__in=("presente", "ausente"),
                        registrada_por__isnull=False,
                        registrada_en__isnull=False,
                    )
                ),
                name="asistencia_estado_y_registro_validos",
                violation_error_message="Una asistencia presente o ausente debe tener responsable y momento de registro.",
            ),
        ]
        verbose_name = "asistencia"
        verbose_name_plural = "asistencias"

    def __str__(self):
        return f"{self.clase} - {self.usuario}: {self.get_estado_display()}"
