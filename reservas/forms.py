from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone

from instalaciones.models import Cancha, Sede
from usuarios.models import Usuario

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


class CanchaReservaRadioSelect(forms.RadioSelect):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            opcion["attrs"]["data-sede"] = value.instance.sede_id
        return opcion


class OrganizadorReservaField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        return f"{usuario} ({usuario.username})"


class CanchaReservaField(forms.ModelChoiceField):
    def label_from_instance(self, cancha):
        return cancha.nombre


class ReservaDatosForm(forms.Form):
    organizador = OrganizadorReservaField(
        queryset=Usuario.objects.none(),
        empty_label="Elegí un organizador",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.none(),
        empty_label="Elegí una sede",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    cancha = CanchaReservaField(
        queryset=Cancha.objects.none(),
        empty_label=None,
        widget=CanchaReservaRadioSelect(),
    )
    fecha = forms.DateField(
        label="Fecha de uso",
        input_formats=["%Y-%m-%d"],
        validators=[validar_fecha_reserva],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date", "form": "reserva-datos"}),
    )
    def __init__(self, *args, es_administrador, **kwargs):
        super().__init__(*args, **kwargs)
        if es_administrador:
            self.fields["organizador"].queryset = Usuario.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        else:
            self.fields.pop("organizador")
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


class ReservaTurnosForm(forms.Form):
    turnos = forms.TypedMultipleChoiceField(
        label="Turnos",
        coerce=int,
        error_messages={
            "required": "Seleccioná al menos un turno.",
            "invalid_choice": "Uno o más turnos ya no están disponibles. Elegí nuevamente.",
        },
    )
    precio_reserva = forms.IntegerField(min_value=1, widget=forms.HiddenInput())
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, turnos, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turnos"].choices = [
            (str(turno.pk), f"{turno.hora_inicio:%H:%M} a {turno.hora_fin:%H:%M}")
            for turno in turnos
        ]

    def clean_turnos(self):
        turnos = self.cleaned_data["turnos"]
        if len(turnos) != len(set(turnos)):
            raise forms.ValidationError("No se puede seleccionar un mismo turno más de una vez.")
        return turnos
