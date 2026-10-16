from decimal import Decimal

from django import forms

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda
from instalaciones.models import Cancha, Sede
from reservas.forms import CanchaReservaField, OrganizadorReservaField
from usuarios.models import Rol, Usuario


class AgendaFiltroForm(forms.Form):
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.all(),
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    cancha = CanchaReservaField(
        queryset=Cancha.objects.none(),
        required=False,
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fecha = forms.DateField(
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    hora = forms.TypedChoiceField(
        choices=[(str(hora), str(hora)) for hora in range(23)],
        coerce=int,
        required=False,
        empty_value=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fecha_maxima = fecha_maxima_agenda()
        self.fields["fecha"].widget.attrs.update({
            "min": FECHA_INICIO_OPERACIONES.isoformat(),
            "max": self.fecha_maxima.isoformat(),
        })
        sede = self.data.get("sede", "")
        if str(sede).isdigit():
            self.fields["cancha"].queryset = Cancha.objects.filter(sede_id=sede).select_related("sede").order_by("estado", "nombre")

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if not FECHA_INICIO_OPERACIONES <= fecha <= self.fecha_maxima:
            raise forms.ValidationError(
                f"Elegí una fecha entre el {FECHA_INICIO_OPERACIONES:%d/%m/%Y} y el {self.fecha_maxima:%d/%m/%Y}."
            )
        return fecha

    def clean(self):
        datos = super().clean()
        sede = datos.get("sede")
        cancha = datos.get("cancha")
        if sede and cancha and cancha.sede_id != sede.pk:
            self.add_error("cancha", "Elegí una cancha de la sede seleccionada.")
        if sede and cancha is None and "cancha" not in self.errors:
            datos["cancha"] = self.fields["cancha"].queryset.first()
        return datos


class AgendaReservaForm(forms.Form):
    organizador = OrganizadorReservaField(
        queryset=Usuario.objects.filter(
            is_active=True,
            roles__rol__codigo__in=(Rol.RESERVAS, Rol.ADMINISTRADOR),
        ).distinct().order_by("first_name", "last_name", "username"),
        empty_label="Elegí un organizador",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    precio_mostrado = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.HiddenInput(),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
