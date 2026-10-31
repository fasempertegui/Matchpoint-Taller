from django import forms
from django.utils import formats, timezone

from common.fechas import FECHA_INICIO_OPERACIONES
from usuarios.models import Rol, Usuario

from .fechas import meses_contratables, validar_fecha_alta, validar_mes_contratacion
from .models import Pase, Plan, PlanUsuario


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


class PaseForm(forms.ModelForm):
    version = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Pase
        fields = (
            "nombre", "tipo", "limite_horas_diarias", "precio_vigente", "precio_invitado_vigente",
            "descripcion",
        )
        localized_fields = ("precio_vigente", "precio_invitado_vigente")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "limite_horas_diarias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "precio_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "precio_invitado_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"].required = self.instance.pk is not None


class SeleccionContratacionPlanForm(forms.Form):
    usuario = forms.ModelChoiceField(
        label="Usuario", queryset=Usuario.objects.none(), widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Elegí una cuenta activa. Quienes tienen rol Profesor no pueden contratar planes.",
    )
    plan = forms.ModelChoiceField(
        label="Plan", queryset=Plan.objects.none(), widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = Usuario.objects.filter(is_active=True).exclude(
            roles__rol__codigo=Rol.PROFESOR,
        ).order_by("last_name", "first_name", "username")
        self.fields["plan"].queryset = Plan.objects.filter(estado=Plan.Estado.ACTIVO)


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
        help_text="Es independiente del mes cubierto y no puede ser futura.",
    )
    precio_aplicado = forms.DecimalField(
        label="Importe acordado (ARS)", min_value=0, max_digits=12, decimal_places=2, localize=True,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal"}),
        help_text="Se propone el precio vigente. Podés ajustarlo; este importe no registra un cobro.",
    )
    observaciones = forms.CharField(
        label="Observaciones", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes_cubierto"].widget.choices = [
            (mes.isoformat(), f"{formats.date_format(mes, 'F Y')} · {mes:%d/%m/%Y} al "
             f"{PlanUsuario(mes_cubierto=mes).fecha_fin:%d/%m/%Y}")
            for mes in meses_contratables()
        ]
        self.fields["fecha_alta"].widget.attrs.update({
            "min": FECHA_INICIO_OPERACIONES.isoformat(), "max": timezone.localdate().isoformat(),
        })
