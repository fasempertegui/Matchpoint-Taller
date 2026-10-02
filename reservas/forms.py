from django import forms

from .models import PrecioReserva


class PrecioReservaForm(forms.ModelForm):
    class Meta:
        model = PrecioReserva
        fields = ("duracion_horas", "precio_vigente")
        localized_fields = ("precio_vigente",)
        widgets = {
            "duracion_horas": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "numeric",
                    "autofocus": True,
                }
            ),
            "precio_vigente": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "decimal"}
            ),
        }

    def __init__(self, *args, sede, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.sede = sede
        if self.instance.pk:
            self.fields["duracion_horas"].disabled = True
            self.fields["duracion_horas"].help_text = "La duración se define al crear la tarifa."
            self.fields["duracion_horas"].widget.attrs.pop("autofocus", None)
            self.fields["precio_vigente"].widget.attrs["autofocus"] = True

    def clean_duracion_horas(self):
        duracion = self.cleaned_data["duracion_horas"]
        if self.instance.estado == PrecioReserva.Estado.ACTIVO:
            precios = PrecioReserva.objects.filter(
                sede=self.instance.sede,
                duracion_horas=duracion,
                estado=PrecioReserva.Estado.ACTIVO,
            )
            if self.instance.pk:
                precios = precios.exclude(pk=self.instance.pk)
            if precios.exists():
                raise forms.ValidationError(
                    "Ya existe una tarifa activa para esa duración en esta sede."
                )
        return duracion


class PrecioReservaFiltroForm(forms.Form):
    estado = forms.ChoiceField(
        required=False,
        choices=(("", "Todos"), *PrecioReserva.Estado.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    duracion_horas = forms.IntegerField(
        label="Duración en horas",
        required=False,
        min_value=1,
        max_value=24,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric"}),
    )


class PrecioReservaEstadoForm(forms.Form):
    estado = forms.ChoiceField(
        choices=PrecioReserva.Estado.choices,
        widget=forms.HiddenInput(),
    )
