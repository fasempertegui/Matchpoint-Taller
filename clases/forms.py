from django import forms
from django.db.models import Q

from bloqueos.models import Bloqueo
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda
from instalaciones.models import Cancha, Sede
from reservas.models import Evento
from usuarios.models import Rol, Usuario

from .models import Asistencia, TurnoPlanilla


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


class ClaseCanchaForm(forms.Form):
    cancha = forms.ModelChoiceField(
        label="Cancha de destino",
        queryset=Cancha.objects.none(), empty_label="Elegí una cancha",
        widget=forms.Select(attrs={"class": "form-control"}),
        error_messages={
            "required": "Elegí la cancha de destino.",
            "invalid_choice": "Esa cancha ya no está disponible para este turno. Elegí otra y revisá el cambio.",
        },
    )

    def __init__(self, *args, clase, **kwargs):
        super().__init__(*args, **kwargs)
        turno = clase.evento.turno
        ocupadas = Evento.objects.filter(
            turno__fecha=turno.fecha, turno__hora_inicio=turno.hora_inicio,
        ).exclude(estado=Evento.Estado.ANULADO).values("turno__cancha_id")
        self.fields["cancha"].queryset = Cancha.objects.filter(
            Q(sede__horarios__dia_semana=turno.fecha.isoweekday()) & (
                Q(sede__horarios__hora_inicio_1__lte=turno.hora_inicio, sede__horarios__hora_fin_1__gte=turno.hora_fin)
                | Q(sede__horarios__hora_inicio_2__lte=turno.hora_inicio, sede__horarios__hora_fin_2__gte=turno.hora_fin)
            ),
            estado=Cancha.Estado.ACTIVA, sede__estado=Sede.Estado.ACTIVA,
        ).exclude(pk=turno.cancha_id).exclude(pk__in=ocupadas).select_related("sede").order_by("sede__nombre", "nombre", "pk")


class ClaseAnulacionForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de anulación",
        error_messages={"required": "Indicá el motivo de la anulación."},
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    motivo_bloqueo = forms.ChoiceField(
        label="Motivo del bloqueo", choices=(("", "Elegí un motivo"), *Bloqueo.Motivo.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    observaciones = forms.CharField(
        label="Observaciones del bloqueo", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, bloquear, **kwargs):
        super().__init__(*args, **kwargs)
        if not bloquear:
            self.fields.pop("motivo_bloqueo")
            self.fields.pop("observaciones")


class AsistenciaFilaForm(forms.Form):
    usuario = forms.IntegerField(min_value=1, widget=forms.HiddenInput())
    estado = forms.ChoiceField(choices=Asistencia.Estado.choices, widget=forms.HiddenInput())
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"hidden": True}))


class AsistenciaBaseFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        ids = [fila.cleaned_data["usuario"] for fila in self.forms if fila.cleaned_data]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError("No se puede repetir una persona en la carga de asistencia.")
        if Usuario.objects.filter(pk__in=ids).count() != len(ids):
            raise forms.ValidationError("Alguna persona ya no está disponible. Revisá la carga de asistencia.")


AsistenciaFormSet = forms.formset_factory(AsistenciaFilaForm, formset=AsistenciaBaseFormSet, extra=0)


class AsistenciaEditorForm(forms.Form):
    estado = forms.ChoiceField(choices=Asistencia.Estado.choices, widget=forms.RadioSelect())
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
