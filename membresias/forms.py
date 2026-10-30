from django import forms

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
