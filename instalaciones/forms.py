from decimal import Decimal

from django import forms

from .models import Cancha, Sede, SedeHorario


class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ("nombre", "direccion", "observaciones")
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Club Norte",
                    "autofocus": True,
                }
            ),
            "direccion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Avenida Sarmiento 320",
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


class SedePrecioForm(forms.ModelForm):
    precio_mostrado = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Sede
        fields = ("precio_reserva_vigente",)
        localized_fields = ("precio_reserva_vigente",)
        widgets = {
            "precio_reserva_vigente": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "decimal", "autofocus": True}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["precio_reserva_vigente"].required = True
        self.fields["precio_mostrado"].initial = self.instance.precio_reserva_vigente


class CanchaForm(forms.ModelForm):
    class Meta:
        model = Cancha
        fields = ("nombre", "superficie", "observaciones")
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Cancha 1",
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


class SedeHorarioForm(forms.ModelForm):
    class Meta:
        model = SedeHorario
        fields = ("hora_inicio_1", "hora_fin_1", "hora_inicio_2", "hora_fin_2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.required = False
            campo.input_formats = ["%H:%M"]
            campo.widget = forms.TimeInput(
                format="%H:%M",
                attrs={"class": "form-control", "type": "time", "step": "3600"},
            )
