from django import forms
from django.utils import formats, timezone

from common.fechas import FECHA_INICIO_OPERACIONES
from usuarios.models import Rol, Usuario

from .fechas import (
    meses_contratables, meses_contratables_propios, validar_fecha_alta,
    validar_mes_contratacion, validar_mes_contratacion_propia,
)
from .models import AjusteHorasMembresia, Membresia, Plan


class PlanForm(forms.ModelForm):
    version = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Plan
        fields = (
            "nombre", "modalidad", "frecuencia_semanal", "cantidad_clases_por_encuentro",
            "precio_vigente", "descripcion",
        )
        localized_fields = ("precio_vigente",)
        labels = {"precio_vigente": "Precio mensual"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "modalidad": forms.Select(attrs={"class": "form-control"}),
            "frecuencia_semanal": forms.Select(attrs={"class": "form-control"}),
            "cantidad_clases_por_encuentro": forms.Select(attrs={"class": "form-control"}),
            "precio_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "placeholder": "Pesos argentinos"}),
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
        usuarios = Usuario.objects.habilitados()
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
        help_text="El mes siguiente se habilita desde el día 25 inclusive.",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fecha_alta = forms.DateField(
        label="Fecha efectiva de alta", validators=[validar_fecha_alta],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
        help_text="Es independiente del mes cubierto y no puede ser futura",
    )
    revision_precio = forms.CharField(widget=forms.HiddenInput())
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
        min_length=5,
        label="Motivo de anulación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "autofocus": True}),
        error_messages={"required": "Indicá el motivo de la anulación."},
    )


class MembresiaForm(forms.ModelForm):
    version = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Membresia
        fields = ("nombre", "horas_organizador", "horas_invitado", "precio_vigente", "precio_invitado_vigente", "descripcion")
        localized_fields = ("precio_vigente", "precio_invitado_vigente")
        labels = {
            "precio_vigente": "Precio mensual",
            "precio_invitado_vigente": "Adicional por invitado sin beneficio",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "horas_organizador": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "horas_invitado": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "precio_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "placeholder": "Pesos argentinos"}),
            "precio_invitado_vigente": forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "placeholder": "Pesos argentinos"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"].required = self.instance.pk is not None
        if self.instance.pk and self.instance.contrataciones.exists():
            for nombre in ("horas_organizador", "horas_invitado"):
                self.fields[nombre].disabled = True
                self.fields[nombre].help_text = "El cupo se conserva porque esta membresía tiene contrataciones."


class SeleccionContratacionMembresiaForm(SeleccionContratacionPlanForm):
    campo_producto = "membresia"
    modelo_producto = Membresia
    admite_profesor = True
    plan = None
    membresia = forms.ModelChoiceField(
        label="Membresía", queryset=Membresia.objects.none(), empty_label="Seleccioná una membresía",
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class ContratacionMembresiaForm(ContratacionPlanForm):
    plan = None
    membresia = forms.IntegerField(widget=forms.HiddenInput())


class ContratacionMembresiaPropiaForm(forms.Form):
    membresia = forms.ModelChoiceField(
        label="Membresía", queryset=Membresia.objects.none(), empty_label="Seleccioná una membresía",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    mes_cubierto = forms.DateField(
        label="Mes cubierto", widget=forms.Select(attrs={"class": "form-control"}),
        help_text="El mes siguiente se habilita desde el día 25 inclusive. Se cubre el mes completo.",
    )
    observaciones = forms.CharField(
        label="Observaciones", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["membresia"].queryset = Membresia.objects.filter(estado=Membresia.Estado.ACTIVO)
        self.fields["mes_cubierto"].widget.choices = [
            (mes.isoformat(), formats.date_format(mes, "F Y").capitalize())
            for mes in meses_contratables_propios()
        ]

    def clean_mes_cubierto(self):
        mes = self.cleaned_data["mes_cubierto"]
        validar_mes_contratacion_propia(mes)
        return mes


class RenovacionPlanPropioForm(forms.Form):
    observaciones = forms.CharField(
        label="Observaciones", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class ConfirmacionContratacionPropiaForm(forms.Form):
    revision = forms.CharField(widget=forms.HiddenInput())


class AjusteHorasForm(forms.Form):
    tipo_horas = forms.ChoiceField(label="Tipo de horas", choices=AjusteHorasMembresia.TipoHoras.choices,
                                  widget=forms.Select(attrs={"class": "form-control"}))
    operacion = forms.ChoiceField(label="Operación", choices=AjusteHorasMembresia.Operacion.choices,
                                 widget=forms.Select(attrs={"class": "form-control"}))
    cantidad = forms.IntegerField(label="Cantidad de horas", min_value=1, max_value=32767,
                                  widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "step": 1}))
    motivo = forms.CharField(min_length=5, label="Motivo", help_text="El titular podrá consultar este motivo.",
                             widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))

    def __init__(self, *args, reversion=False, **kwargs):
        super().__init__(*args, **kwargs)
        if reversion:
            for campo in ("tipo_horas", "operacion", "cantidad"):
                self.fields.pop(campo)
