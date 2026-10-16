from copy import deepcopy

from django import forms

from reservas.forms import ReservaAnulacionForm

from .models import Bloqueo


class BloqueoForm(forms.Form):
    evento_esperado = forms.IntegerField(min_value=0, widget=forms.HiddenInput())
    motivo = forms.ChoiceField(
        label="Motivo del bloqueo",
        choices=(("", "Elegí un motivo"), *Bloqueo.Motivo.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    motivo_anulacion = deepcopy(ReservaAnulacionForm.base_fields["motivo"])

    def __init__(self, *args, anula_reserva=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not anula_reserva:
            self.fields.pop("motivo_anulacion")


class BloqueoAnulacionForm(forms.Form):
    bloqueo = forms.IntegerField(min_value=1, widget=forms.HiddenInput())
    motivo = forms.CharField(
        label="Motivo de anulación",
        error_messages={"required": "Indicá el motivo de la anulación."},
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
