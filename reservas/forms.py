from decimal import Decimal

from django import forms

from .models import PrecioReserva


class PrecioReservaForm(forms.Form):
    importe = forms.DecimalField(
        label="Precio por turno (ARS)",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        localize=True,
        help_text="Importe por un turno de una hora, común a todas las canchas de la sede.",
        widget=forms.TextInput(
            attrs={"class": "form-control", "inputmode": "decimal", "autofocus": True}
        ),
    )


class PrecioReservaFiltroForm(forms.Form):
    estado = forms.ChoiceField(
        required=False,
        choices=(("", "Todos"), *PrecioReserva.Estado.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
