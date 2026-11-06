from django import forms
from django.utils import formats, timezone

from common.fechas import FECHA_INICIO_OPERACIONES
from usuarios.models import Rol, Usuario

from .fechas import meses_contratables, validar_fecha_alta, validar_mes_contratacion
from .models import Plan


class PlanForm(forms.ModelForm):
    version = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Plan
        fields = (
            "nombre", "modalidad", "frecuencia_semanal", "cantidad_clases_por_encuentro",
            "precio_vigente", "descripcion",
        )
        localized_fields = ("precio_vigente",)
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "modalidad": forms.Select(attrs={"class": "form-control"}),
            "frecuencia_semanal": forms.Select(attrs={"class": "form-control"}),
            "cantidad_clases_por_encuentro": forms.Select(attrs={"class": "form-control"}),
            "precio_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"].required = self.instance.pk is not None
        if self.instance.pk and self.instance.contrataciones.exists():
            for nombre in ("modalidad", "frecuencia_semanal", "cantidad_clases_por_encuentro"):
                self.fields[nombre].disabled = True
                self.fields[nombre].help_text = "La configuración se conserva porque este plan tiene contrataciones."


class SeleccionContratacionPlanForm(forms.Form):
    campo_producto = "plan"
    modelo_producto = Plan
    admite_profesor = False

    usuario = forms.ModelChoiceField(
        label="Usuario", queryset=Usuario.objects.none(), widget=forms.HiddenInput(),
        help_text="Solo se muestran cuentas activas",
    )
    plan = forms.ModelChoiceField(
        label="Plan", queryset=Plan.objects.none(), empty_label="Seleccioná un plan",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuarios = Usuario.objects.filter(is_active=True)
        if not self.admite_profesor:
            usuarios = usuarios.exclude(roles__rol__codigo=Rol.PROFESOR)
        self.fields["usuario"].queryset = usuarios.order_by("last_name", "first_name", "username")
        self.fields[self.campo_producto].queryset = self.modelo_producto.objects.filter(
            estado=self.modelo_producto.Estado.ACTIVO,
        )


class ContratacionPlanForm(forms.Form):
    usuario = forms.IntegerField(widget=forms.HiddenInput())
    plan = forms.IntegerField(widget=forms.HiddenInput())
    mes_cubierto = forms.DateField(
        label="Mes cubierto", validators=[validar_mes_contratacion],
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fecha_alta = forms.DateField(
        label="Fecha efectiva de alta", validators=[validar_fecha_alta],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
        help_text="Es independiente del mes cubierto y no puede ser futura",
    )
    precio_aplicado = forms.DecimalField(
        label="Importe acordado (ARS)", min_value=0, max_digits=12, decimal_places=2, localize=True,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
        help_text="El precio acordado puede ser diferente al precio vigente por descuentos o recargos",
    )
    observaciones = forms.CharField(
        label="Observaciones", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes_cubierto"].widget.choices = [
            (mes.isoformat(), formats.date_format(mes, "F Y").capitalize())
            for mes in meses_contratables()
        ]
        self.fields["fecha_alta"].widget.attrs.update({
            "min": FECHA_INICIO_OPERACIONES.isoformat(), "max": timezone.localdate().isoformat(),
        })


class AnulacionContratacionForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput())
    motivo = forms.CharField(
        label="Motivo de anulación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "autofocus": True}),
        error_messages={"required": "Indicá el motivo de la anulación."},
    )
