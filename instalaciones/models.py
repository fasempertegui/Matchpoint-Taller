from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db.models.lookups import GreaterThanOrEqual

from common.fechas import FECHA_INICIO_OPERACIONES

from .direcciones import (
    LOCALIDADES_SALTA,
    LOCALIDAD_CHOICES,
    PROVINCIA_NOMBRE,
    componer_direccion,
    etiqueta_localidad,
)
from .ubicacion import (
    LATITUD_MAX,
    LATITUD_MIN,
    LONGITUD_MAX,
    LONGITUD_MIN,
    enlaces_mapa,
)


HORAS_EN_PUNTO = tuple(time(hora) for hora in range(24))


def _validar_franjas_horarias(hora_inicio_1, hora_fin_1, hora_inicio_2, hora_fin_2):
    errores = {}
    if hora_inicio_1 is None:
        errores["hora_inicio_1"] = "Indicá el inicio de la primera franja."
    if hora_fin_1 is None:
        errores["hora_fin_1"] = "Indicá el fin de la primera franja."
    if (
        hora_inicio_1 is not None
        and hora_fin_1 is not None
        and hora_fin_1 <= hora_inicio_1
    ):
        errores["hora_fin_1"] = "El fin debe ser posterior al inicio."

    if hora_inicio_2 is None and hora_fin_2 is not None:
        errores["hora_inicio_2"] = "Indicá el inicio de la segunda franja."
    if hora_fin_2 is None and hora_inicio_2 is not None:
        errores["hora_fin_2"] = "Indicá el fin de la segunda franja."
    if hora_inicio_2 is not None and hora_fin_2 is not None:
        if hora_fin_2 <= hora_inicio_2:
            errores["hora_fin_2"] = "El fin debe ser posterior al inicio."
        if hora_fin_1 is not None:
            fin_primera = datetime.combine(date.min, hora_fin_1)
            inicio_segunda = datetime.combine(date.min, hora_inicio_2)
            if inicio_segunda - fin_primera < timedelta(hours=1):
                errores["hora_inicio_2"] = (
                    "La segunda franja debe comenzar al menos una hora después de terminar la primera."
                )

    for nombre, hora in (
        ("hora_inicio_1", hora_inicio_1),
        ("hora_fin_1", hora_fin_1),
        ("hora_inicio_2", hora_inicio_2),
        ("hora_fin_2", hora_fin_2),
    ):
        if hora is not None and hora not in HORAS_EN_PUNTO:
            errores[nombre] = "Ingresá una hora en punto, por ejemplo 09:00."

    return errores


class Sede(models.Model):

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    SERVICIOS = (
        ("tiene_estacionamiento", "Estacionamiento"),
        ("tiene_sanitarios", "Sanitarios"),
        ("tiene_vestuarios", "Vestuarios"),
        ("tiene_wifi", "Wi-Fi"),
        ("tiene_buffet", "Buffet"),
    )

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=250)
    localidad_codigo = models.CharField(
        "Localidad",
        max_length=8,
        choices=LOCALIDAD_CHOICES,
        blank=True,
        default="",
    )
    calle = models.CharField("Calle", max_length=150, blank=True, default="")
    altura = models.CharField("Altura", max_length=20, blank=True, default="")
    cpa = models.CharField("CPA", max_length=8, blank=True, default="")
    calle_georef_id = models.CharField(
        "ID de calle en Georef",
        max_length=20,
        blank=True,
        default="",
    )
    latitud = models.DecimalField(
        "Latitud",
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    longitud = models.DecimalField(
        "Longitud",
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    tiene_estacionamiento = models.BooleanField("Estacionamiento", default=False)
    tiene_sanitarios = models.BooleanField("Sanitarios", default=False)
    tiene_vestuarios = models.BooleanField("Vestuarios", default=False)
    tiene_wifi = models.BooleanField("Wi-Fi", default=False)
    tiene_buffet = models.BooleanField("Buffet", default=False)
    telefono_contacto_1 = models.CharField("Teléfono principal", max_length=30, blank=True, default="")
    telefono_contacto_2 = models.CharField("Teléfono adicional", max_length=30, blank=True, default="")
    precio_reserva_vigente = models.DecimalField(
        "Precio por turno (ARS)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        blank=True,
        null=True,
        help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
    )
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
            models.CheckConstraint(
                condition=(
                    models.Q(precio_reserva_vigente__isnull=True)
                    | models.Q(precio_reserva_vigente__gte=Decimal("0.01"))
                ),
                name="sede_precio_reserva_positivo",
                violation_error_message="El precio por turno debe ser positivo.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(localidad_codigo="")
                    | models.Q(localidad_codigo__in=tuple(LOCALIDADES_SALTA))
                ),
                name="sede_localidad_codigo_habilitado",
                violation_error_message="La localidad seleccionada no está habilitada.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        localidad_codigo="",
                        calle="",
                        altura="",
                        cpa="",
                        calle_georef_id="",
                    )
                    | (
                        ~models.Q(localidad_codigo="")
                        & ~models.Q(calle="")
                        & ~models.Q(altura="")
                    )
                ),
                name="sede_direccion_estructurada_coherente",
                violation_error_message="La dirección estructurada requiere localidad, calle y altura.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(latitud__isnull=True, longitud__isnull=True)
                    | models.Q(latitud__isnull=False, longitud__isnull=False)
                ),
                name="sede_coordenadas_completas",
                violation_error_message="La latitud y la longitud deben informarse juntas.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(latitud__isnull=True)
                    | models.Q(latitud__gte=LATITUD_MIN, latitud__lte=LATITUD_MAX)
                ),
                name="sede_latitud_rango",
                violation_error_message="La latitud debe estar entre -90 y 90.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(longitud__isnull=True)
                    | models.Q(longitud__gte=LONGITUD_MIN, longitud__lte=LONGITUD_MAX)
                ),
                name="sede_longitud_rango",
                violation_error_message="La longitud debe estar entre -180 y 180.",
            ),
        ]
        verbose_name = "sede"
        verbose_name_plural = "sedes"

    def __str__(self):
        return self.nombre

    @property
    def servicios_disponibles(self):
        return [etiqueta for campo, etiqueta in self.SERVICIOS if getattr(self, campo)]

    @property
    def telefonos_contacto(self):
        return [
            telefono
            for telefono in (self.telefono_contacto_1, self.telefono_contacto_2)
            if telefono
        ]

    @property
    def tiene_direccion_estructurada(self):
        return bool(self.localidad_codigo and self.calle and self.altura)

    @property
    def localidad_nombre(self):
        return etiqueta_localidad(self.localidad_codigo)

    @property
    def provincia_nombre(self):
        return PROVINCIA_NOMBRE if self.tiene_direccion_estructurada else ""

    @property
    def direccion_completa(self):
        if self.tiene_direccion_estructurada:
            return componer_direccion(
                self.calle,
                self.altura,
                self.localidad_codigo,
                self.cpa,
            )
        return self.direccion

    @property
    def origen_calle_display(self):
        if not self.tiene_direccion_estructurada:
            return ""
        if self.calle_georef_id:
            return "Normalizada con Georef"
        return "Carga manual confirmada"

    @property
    def tiene_ubicacion(self):
        return self.latitud is not None and self.longitud is not None

    @property
    def enlaces_ubicacion(self):
        return enlaces_mapa(self.latitud, self.longitud)


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
                condition=(
                    models.Q(
                        hora_inicio_1__in=HORAS_EN_PUNTO,
                        hora_fin_1__in=HORAS_EN_PUNTO,
                    )
                    & (
                        models.Q(hora_inicio_2__isnull=True)
                        | models.Q(hora_inicio_2__in=HORAS_EN_PUNTO)
                    )
                    & (
                        models.Q(hora_fin_2__isnull=True)
                        | models.Q(hora_fin_2__in=HORAS_EN_PUNTO)
                    )
                ),
                name="sede_horario_horas_en_punto",
                violation_error_message="Los horarios deben ser en punto.",
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
                    | GreaterThanOrEqual(
                        models.F("hora_inicio_2") - models.F("hora_fin_1"),
                        models.Value(timedelta(hours=1)),
                    )
                ),
                name="sede_horario_pausa_minima",
                violation_error_message="Debe haber al menos una hora sin funcionamiento entre las dos franjas.",
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

        errores = _validar_franjas_horarias(*horas)
        if errores:
            raise ValidationError(errores)


class SedeHorarioEspecial(models.Model):
    id = models.BigAutoField(primary_key=True)
    sede = models.ForeignKey(
        Sede,
        on_delete=models.PROTECT,
        related_name="horarios_especiales",
    )
    fecha = models.DateField()
    motivo = models.CharField(max_length=150)
    cerrada = models.BooleanField(default=False)
    hora_inicio_1 = models.TimeField("Inicio de la primera franja", blank=True, null=True)
    hora_fin_1 = models.TimeField("Fin de la primera franja", blank=True, null=True)
    hora_inicio_2 = models.TimeField("Inicio de la segunda franja", blank=True, null=True)
    hora_fin_2 = models.TimeField("Fin de la segunda franja", blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sedes_horarios_especiales"
        ordering = ("fecha", "sede__nombre")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("sede", "fecha"),
                name="sede_horario_especial_sede_fecha_unico",
                violation_error_message="Ya existe un horario especial para esta sede en esa fecha.",
            ),
            models.CheckConstraint(
                condition=models.Q(fecha__gte=FECHA_INICIO_OPERACIONES),
                name="sede_horario_especial_fecha_operativa",
                violation_error_message=(
                    f"La fecha no puede ser anterior al {FECHA_INICIO_OPERACIONES:%d/%m/%Y}."
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(motivo__regex=r"\S"),
                name="sede_horario_especial_motivo_informado",
                violation_error_message="Indicá el motivo del horario especial.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        cerrada=True,
                        hora_inicio_1__isnull=True,
                        hora_fin_1__isnull=True,
                        hora_inicio_2__isnull=True,
                        hora_fin_2__isnull=True,
                    )
                    | models.Q(
                        cerrada=False,
                        hora_inicio_1__isnull=False,
                        hora_fin_1__isnull=False,
                    )
                ),
                name="sede_horario_especial_estado_franjas",
                violation_error_message=(
                    "Si la sede está cerrada no debe tener franjas; "
                    "si está abierta debe tener al menos la primera franja."
                ),
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(hora_inicio_1__isnull=True)
                        | models.Q(hora_inicio_1__in=HORAS_EN_PUNTO)
                    )
                    & (
                        models.Q(hora_fin_1__isnull=True)
                        | models.Q(hora_fin_1__in=HORAS_EN_PUNTO)
                    )
                    & (
                        models.Q(hora_inicio_2__isnull=True)
                        | models.Q(hora_inicio_2__in=HORAS_EN_PUNTO)
                    )
                    & (
                        models.Q(hora_fin_2__isnull=True)
                        | models.Q(hora_fin_2__in=HORAS_EN_PUNTO)
                    )
                ),
                name="sede_horario_especial_horas_en_punto",
                violation_error_message="Los horarios deben ser en punto.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_1__isnull=True)
                    | models.Q(hora_fin_1__gt=models.F("hora_inicio_1"))
                ),
                name="sede_horario_especial_primera_franja_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True, hora_fin_2__isnull=True)
                    | models.Q(hora_inicio_2__isnull=False, hora_fin_2__isnull=False)
                ),
                name="sede_horario_especial_segunda_franja_completa",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True)
                    | models.Q(hora_fin_2__gt=models.F("hora_inicio_2"))
                ),
                name="sede_horario_especial_segunda_franja_valida",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(hora_inicio_2__isnull=True)
                    | GreaterThanOrEqual(
                        models.F("hora_inicio_2") - models.F("hora_fin_1"),
                        models.Value(timedelta(hours=1)),
                    )
                ),
                name="sede_horario_especial_pausa_minima",
                violation_error_message="Debe haber al menos una hora sin funcionamiento entre las dos franjas.",
            ),
        ]
        verbose_name = "horario especial de sede"
        verbose_name_plural = "horarios especiales de sede"

    def __str__(self):
        return f"{self.sede} - {self.fecha:%d/%m/%Y}"

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha is not None and self.fecha < FECHA_INICIO_OPERACIONES:
            errores["fecha"] = (
                f"La fecha no puede ser anterior al {FECHA_INICIO_OPERACIONES:%d/%m/%Y}."
            )
        if self.motivo is not None and not self.motivo.strip():
            errores["motivo"] = "Indicá el motivo del horario especial."

        if self.cerrada:
            for nombre in ("hora_inicio_1", "hora_fin_1", "hora_inicio_2", "hora_fin_2"):
                if getattr(self, nombre) is not None:
                    errores[nombre] = "No podés cargar horarios si la sede está cerrada."
        else:
            errores.update(
                _validar_franjas_horarias(
                    self.hora_inicio_1,
                    self.hora_fin_1,
                    self.hora_inicio_2,
                    self.hora_fin_2,
                )
            )

        if errores:
            raise ValidationError(errores)
