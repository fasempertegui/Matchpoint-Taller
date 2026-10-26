from django import forms


class ReservaAnulacionForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de anulación",
        min_length=25,
        help_text="Mínimo 25 caracteres",
        error_messages={
            "required": "Indicá el motivo de la anulación.",
            "min_length": "El motivo de anulación debe tener al menos 25 caracteres.",
        },
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
