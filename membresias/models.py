from calendar import monthrange
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from common.fechas import FECHA_INICIO_OPERACIONES


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
        ordering = ("modalidad", "cantidad_clases_por_encuentro", "frecuencia_semanal", "nombre", "pk")
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


class Pase(models.Model):
    class Tipo(models.TextChoices):
        LIBRE = "libre", "Libre"
        FIN_DE_SEMANA = "fin_de_semana", "Fin de semana"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField("Descripción", blank=True, default="")
    tipo = models.CharField("Variante", max_length=15, choices=Tipo.choices)
    limite_horas_diarias = models.PositiveSmallIntegerField(
        "Límite de horas por día", default=2, validators=[MinValueValidator(1)],
    )
    precio_vigente = models.DecimalField(
        "Precio mensual (ARS)", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    precio_invitado_vigente = models.DecimalField(
        "Adicional por invitado sin cobertura (ARS)", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Importe por invitado y turno de una hora.",
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pases"
        ordering = ("nombre", "pk")
        default_permissions = ()
        verbose_name = "pase"
        verbose_name_plural = "pases"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"), condition=models.Q(estado="activo"),
                name="pase_nombre_activo_unico",
                violation_error_message="Ya existe un pase activo con ese nombre.",
            ),
            models.CheckConstraint(condition=models.Q(nombre__regex=r"\S"), name="pase_nombre_no_vacio"),
            models.CheckConstraint(
                condition=models.Q(tipo__in=("libre", "fin_de_semana")), name="pase_tipo_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(limite_horas_diarias__gte=1), name="pase_limite_horas_positivo",
            ),
            models.CheckConstraint(condition=models.Q(precio_vigente__gte=0), name="pase_precio_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(precio_invitado_vigente__gte=0), name="pase_precio_invitado_no_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "inactivo")), name="pase_estado_valido",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def dias_habilitados(self):
        return "Sábados y domingos" if self.tipo == self.Tipo.FIN_DE_SEMANA else "Todos los días"


class PlanUsuario(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ANULADO = "anulado", "Anulado"
        VENCIDO = "vencido", "Vencido"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="planes_contratados")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="contrataciones")
    mes_cubierto = models.DateField("Mes cubierto")
    fecha_alta = models.DateField("Fecha efectiva de alta")
    precio_aplicado = models.DecimalField(
        "Importe acordado (ARS)", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contrataciones_plan_registradas",
    )
    observaciones = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    aviso_vencimiento_enviado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contrataciones_plan_anuladas",
        null=True, blank=True,
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planes_usuarios"
        ordering = ("-mes_cubierto", "-pk")
        default_permissions = ()
        verbose_name = "contratación de plan"
        verbose_name_plural = "contrataciones de planes"
        constraints = [
            models.UniqueConstraint(
                fields=("usuario", "mes_cubierto"), condition=models.Q(estado__in=("activo", "vencido")),
                name="plan_usuario_mes_no_anulado_unico",
                violation_error_message="El usuario ya tiene una contratación de plan para ese mes.",
            ),
            models.CheckConstraint(condition=models.Q(mes_cubierto__day=1), name="plan_usuario_mes_primer_dia"),
            models.CheckConstraint(
                condition=models.Q(mes_cubierto__gte=FECHA_INICIO_OPERACIONES), name="plan_usuario_mes_operativo",
            ),
            models.CheckConstraint(condition=models.Q(precio_aplicado__gte=0), name="plan_usuario_precio_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "anulado", "vencido")), name="plan_usuario_estado_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(estado="anulado", anulado_por__isnull=False, anulado_en__isnull=False,
                             motivo_anulacion__regex=r"\S")
                    | (models.Q(anulado_por__isnull=True, anulado_en__isnull=True, motivo_anulacion="")
                       & ~models.Q(estado="anulado"))
                ),
                name="plan_usuario_anulacion_coherente",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} · {self.plan} · {self.mes_cubierto:%m/%Y}"

    @property
    def producto(self):
        return self.plan

    def vigente_en(self, fecha):
        return self.estado == self.Estado.ACTIVO and self.fecha_inicio <= fecha <= self.fecha_fin

    @property
    def fecha_inicio(self):
        return self.mes_cubierto

    @property
    def fecha_fin(self):
        return self.mes_cubierto.replace(day=monthrange(self.mes_cubierto.year, self.mes_cubierto.month)[1])

    def clean(self):
        super().clean()
        if self.mes_cubierto and self.mes_cubierto.day != 1:
            raise ValidationError({"mes_cubierto": "Elegí un mes calendario completo."})
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            campos = ("usuario_id", "plan_id", "mes_cubierto", "fecha_alta", "precio_aplicado", "registrado_por_id")
            if any(getattr(self, campo) != getattr(original, campo) for campo in campos):
                raise ValidationError("Los datos de una contratación registrada no se pueden editar.")


class PaseUsuario(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ANULADO = "anulado", "Anulado"
        VENCIDO = "vencido", "Vencido"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pases_contratados")
    pase = models.ForeignKey(Pase, on_delete=models.PROTECT, related_name="contrataciones")
    mes_cubierto = models.DateField("Mes cubierto")
    fecha_alta = models.DateField("Fecha efectiva de alta")
    precio_aplicado = models.DecimalField(
        "Importe aplicado (ARS)", max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contrataciones_pase_registradas",
    )
    observaciones = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    aviso_vencimiento_enviado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contrataciones_pase_anuladas",
        null=True, blank=True,
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pases_usuarios"
        ordering = ("-mes_cubierto", "-pk")
        default_permissions = ()
        verbose_name = "contratación de pase"
        verbose_name_plural = "contrataciones de pases"
        constraints = [
            models.UniqueConstraint(
                fields=("usuario", "mes_cubierto"), condition=models.Q(estado__in=("activo", "vencido")),
                name="pase_usuario_mes_no_anulado_unico",
                violation_error_message="El usuario ya tiene una contratación de pase para ese mes.",
            ),
            models.CheckConstraint(condition=models.Q(mes_cubierto__day=1), name="pase_usuario_mes_primer_dia"),
            models.CheckConstraint(
                condition=models.Q(mes_cubierto__gte=FECHA_INICIO_OPERACIONES), name="pase_usuario_mes_operativo",
            ),
            models.CheckConstraint(condition=models.Q(precio_aplicado__gte=0), name="pase_usuario_precio_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(estado__in=("activo", "anulado", "vencido")), name="pase_usuario_estado_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(estado="anulado", anulado_por__isnull=False, anulado_en__isnull=False,
                             motivo_anulacion__regex=r"\S")
                    | (models.Q(anulado_por__isnull=True, anulado_en__isnull=True, motivo_anulacion="")
                       & ~models.Q(estado="anulado"))
                ),
                name="pase_usuario_anulacion_coherente",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} · {self.pase} · {self.mes_cubierto:%m/%Y}"

    @property
    def producto(self):
        return self.pase

    def vigente_en(self, fecha):
        return (
            self.estado == self.Estado.ACTIVO and self.fecha_inicio <= fecha <= self.fecha_fin
            and (self.pase.tipo == Pase.Tipo.LIBRE or fecha.weekday() >= 5)
        )

    @property
    def fecha_inicio(self):
        return self.mes_cubierto

    @property
    def fecha_fin(self):
        return self.mes_cubierto.replace(day=monthrange(self.mes_cubierto.year, self.mes_cubierto.month)[1])

    def clean(self):
        super().clean()
        if self.mes_cubierto and self.mes_cubierto.day != 1:
            raise ValidationError({"mes_cubierto": "Elegí un mes calendario completo."})
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            campos = ("usuario_id", "pase_id", "mes_cubierto", "fecha_alta", "precio_aplicado", "registrado_por_id")
            if any(getattr(self, campo) != getattr(original, campo) for campo in campos):
                raise ValidationError("Los datos de una contratación registrada no se pueden editar.")
