from django import forms

from .models import Cancha, Sede


class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ("nombre", "direccion", "observaciones")
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Sociedad Española",
                    "autofocus": True,
                }
            ),
            "direccion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Av. Sarmiento 320",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Información adicional sobre la sede",
                }
            ),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        sedes_con_mismo_nombre = Sede.objects.filter(nombre__iexact=nombre)

        if self.instance.pk:
            sedes_con_mismo_nombre = sedes_con_mismo_nombre.exclude(
                pk=self.instance.pk
            )

        if sedes_con_mismo_nombre.exists():
            raise forms.ValidationError(
                "Ya existe una sede con ese nombre."
            )

        return nombre


class CanchaForm(forms.ModelForm):
    class Meta:
        model = Cancha
        fields = ("nombre", "superficie", "observaciones")
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej.: Cancha 1",
                    "autofocus": True,
                }
            ),
            "superficie": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Información adicional sobre la cancha",
                }
            ),
        }

    def __init__(self, *args, sede, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        canchas_con_mismo_nombre = Cancha.objects.filter(
            sede=self.sede, nombre__iexact=nombre
        )

        if self.instance.pk:
            canchas_con_mismo_nombre = canchas_con_mismo_nombre.exclude(
                pk=self.instance.pk
            )

        if canchas_con_mismo_nombre.exists():
            raise forms.ValidationError(
                "Ya existe una cancha con ese nombre en esta sede."
            )

        return nombre

    def save(self, commit=True):
        cancha = super().save(commit=False)
        cancha.sede = self.sede
        if commit:
            cancha.save()
        return cancha
