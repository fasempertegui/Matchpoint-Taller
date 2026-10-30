from django import forms

from .models import Pase, Plan


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
