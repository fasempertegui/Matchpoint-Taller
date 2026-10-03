from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone

from instalaciones.models import Cancha, Sede

from .disponibilidad import validar_fecha_reserva
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


class CanchaDisponibilidadSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            opcion["attrs"]["data-sede"] = value.instance.sede_id
        return opcion


class DisponibilidadForm(forms.Form):
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.none(),
        empty_label="Elegí una sede",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    cancha = forms.ModelChoiceField(
        queryset=Cancha.objects.none(),
        empty_label="Elegí una cancha",
        widget=CanchaDisponibilidadSelect(attrs={"class": "form-control"}),
    )
    fecha = forms.DateField(
        label="Fecha de uso",
        input_formats=["%Y-%m-%d"],
        validators=[validar_fecha_reserva],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    cantidad_horas = forms.IntegerField(
        label="Cantidad de horas",
        min_value=1,
        max_value=23,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.localdate()
        self.fields["fecha"].initial = hoy
        self.fields["fecha"].widget.attrs.update({
            "min": hoy.isoformat(),
            "max": (hoy + timedelta(days=14)).isoformat(),
        })
        self.fields["sede"].queryset = Sede.objects.filter(
            estado=Sede.Estado.ACTIVA,
            precios_reservas__estado=PrecioReserva.Estado.ACTIVO,
        )
        self.fields["cancha"].queryset = Cancha.objects.filter(
            estado=Cancha.Estado.ACTIVA,
            sede__in=self.fields["sede"].queryset,
        ).select_related("sede")

    def clean(self):
        datos = super().clean()
        sede = datos.get("sede")
        cancha = datos.get("cancha")
        if sede and cancha and cancha.sede_id != sede.pk:
            self.add_error("cancha", "Elegí una cancha de la sede seleccionada.")
        return datos
