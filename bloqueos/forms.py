from django import forms

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

class BloqueoAnulacionForm(forms.Form):
    bloqueo = forms.IntegerField(min_value=1, widget=forms.HiddenInput())
    motivo = forms.CharField(
        min_length=5,
        label="Motivo de anulación",
        error_messages={"required": "Indicá el motivo de la anulación."},
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
