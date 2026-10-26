from django import forms
from django.db.models import Q

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda
from instalaciones.models import Cancha
from usuarios.models import Rol, Usuario

from .models import TurnoPlanilla


class ClaseTurnoForm(forms.Form):
    cancha = forms.ModelChoiceField(queryset=Cancha.objects.select_related("sede"))
    fecha = forms.DateField(input_formats=["%Y-%m-%d"])
    hora = forms.TypedChoiceField(choices=[(hora, hora) for hora in range(23)], coerce=int)

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if not FECHA_INICIO_OPERACIONES <= fecha <= fecha_maxima_agenda():
            raise forms.ValidationError("La fecha está fuera del calendario operativo de clases.")
        return fecha


class ClaseForm(forms.Form):
    profesores = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.none(), widget=forms.MultipleHiddenInput(),
        error_messages={"required": "Agregá al menos un profesor.", "invalid_choice": "Revisá los profesores seleccionados: alguno ya no está habilitado."},
    )
    participantes = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.none(), widget=forms.MultipleHiddenInput(), required=False,
        error_messages={"invalid_choice": "Revisá los participantes seleccionados: alguno ya no está activo."},
    )
    buscar_todos = forms.BooleanField(required=False)
    modalidad = forms.ChoiceField(
        choices=(("", "Sin especificar"), *TurnoPlanilla.Modalidad.choices), required=False,
        widget=forms.RadioSelect(),
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, profesores_actuales=(), participantes_actuales=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profesores"].queryset = Usuario.objects.filter(
            Q(is_active=True, roles__rol__codigo=Rol.PROFESOR) | Q(pk__in=profesores_actuales),
        ).distinct()
        self.fields["participantes"].queryset = Usuario.objects.filter(
            Q(is_active=True) | Q(pk__in=participantes_actuales),
        )

    def clean(self):
        datos = super().clean()
        profesores = {usuario.pk for usuario in datos.get("profesores", [])}
        participantes = {usuario.pk for usuario in datos.get("participantes", [])}
        if profesores & participantes:
            self.add_error("participantes", "Una persona no puede dictar y participar en la misma clase.")
        return datos

    def seleccionados(self, campo):
        valores = self[campo].value() or []
        ids = [int(valor) for valor in valores if str(valor).isdecimal() and len(str(valor)) < 19]
        personas = Usuario.objects.in_bulk(ids)
        return [personas[pk] for pk in dict.fromkeys(ids) if pk in personas]

    def parametros(self):
        return {
            "profesores_ids": {usuario.pk for usuario in self.cleaned_data["profesores"]},
            "participantes_ids": {usuario.pk for usuario in self.cleaned_data["participantes"]},
            "modalidad": self.cleaned_data["modalidad"] or None,
            "observaciones": self.cleaned_data["observaciones"],
        }
