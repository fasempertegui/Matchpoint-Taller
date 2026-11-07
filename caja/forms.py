from decimal import Decimal

from django import forms


class AperturaCajaForm(forms.Form):
    efectivo_inicial = forms.DecimalField(label="Efectivo inicial (ARS)", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}))
    motivo_apertura = forms.CharField(label="Motivo si difiere del último contado", required=False, strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    revision = forms.CharField(widget=forms.HiddenInput())


class CierreCajaForm(forms.Form):
    efectivo_contado = forms.DecimalField(label="Efectivo contado (ARS)", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}))
    motivo_diferencia = forms.CharField(label="Motivo si hay diferencia", required=False, strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
