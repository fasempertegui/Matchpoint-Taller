from datetime import datetime, time
from decimal import Decimal

from django import forms
from django.utils import timezone

from bloqueos.models import Bloqueo
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda, fecha_maxima_eventos, opciones_meses_agenda
from instalaciones.models import Cancha, Sede
from usuarios.models import Rol, Usuario


class CanchaAgendaField(forms.ModelChoiceField):
    def label_from_instance(self, cancha):
        return cancha.nombre


class AgendaFiltroForm(forms.Form):
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.all(),
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    cancha = CanchaAgendaField(
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
    organizador = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(
            is_active=True,
            roles__rol__codigo__in=(Rol.RESERVAS, Rol.ADMINISTRADOR),
        ).distinct().order_by("first_name", "last_name", "username"),
        widget=forms.HiddenInput(),
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

    def __init__(self, *args, es_administrador, **kwargs):
        super().__init__(*args, **kwargs)
        if not es_administrador:
            self.fields.pop("organizador")


class CanchasAgendaField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, cancha):
        return cancha.nombre


class AgendaOperacionForm(forms.Form):
    operacion = forms.ChoiceField(
        label="Operación *",
        choices=(("liberar", "Anular y liberar"), ("bloquear", "Anular y bloquear")),
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="bloquear",
    )
    seleccion_canchas = forms.ChoiceField(
        label="Canchas *",
        choices=(("todas", "Todas las canchas de la sede"), ("seleccionar", "Seleccionar")),
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="todas",
    )
    canchas = CanchasAgendaField(
        label="Elegí las canchas *",
        queryset=Cancha.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    horario = forms.ChoiceField(
        label="Horario *",
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="dia",
        error_messages={"invalid_choice": "Ese horario ya no está disponible. Elegí nuevamente."},
    )
    hora_hasta = forms.ChoiceField(
        label="Hasta",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        error_messages={"invalid_choice": "Elegí una hora de fin posterior al inicio y dentro del horario del día."},
    )
    excluir_clases_manuales = forms.BooleanField(label="Clases creadas manualmente", required=False)
    excluir_clases_generadas = forms.BooleanField(label="Clases generadas desde la planilla", required=False)
    excluir_reservas = forms.BooleanField(label="Reservas", required=False)
    excluir_bloqueos = forms.BooleanField(label="Bloqueos", required=False)
    motivo_bloqueo = forms.ChoiceField(
        label="Motivo del bloqueo *",
        required=False,
        choices=(("", "Elegí un motivo"), *Bloqueo.Motivo.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    motivo_anulacion = forms.CharField(
        min_length=5,
        label="Motivo de anulación *",
        required=False,
        help_text="Mínimo 5 caracteres",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, sede, fecha, **kwargs):
        super().__init__(*args, **kwargs)
        canchas = sede.canchas.order_by("nombre", "pk")
        self.fields["canchas"].queryset = canchas
        if fecha > fecha_maxima_eventos():
            self.fields["operacion"].choices = (("liberar", "Anular y liberar"),)
            self.fields["operacion"].initial = "liberar"
        ahora = timezone.localtime()
        horario = sede.horarios.filter(dia_semana=fecha.isoweekday()).first()
        franjas = []
        if horario is not None:
            franjas.append((horario.hora_inicio_1, horario.hora_fin_1))
            if horario.hora_inicio_2 is not None:
                franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
        self.fields["horario"].choices = [("dia", "Día completo")] + [
            (f"{hora:02d}:00", f"Desde las {hora:02d}:00")
            for hora in range(23)
            if timezone.make_aware(datetime.combine(fecha, time(hora))) > ahora
            and any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
        ]
        desde = self.data.get("horario", "dia")
        inicios = {valor for valor, _ in self.fields["horario"].choices if valor != "dia"}
        finales = sorted(f"{int(inicio[:2]) + 1:02d}:00" for inicio in inicios)
        self.fields["hora_hasta"].choices = [("", "Fin del día")] + [
            (fin, fin) for fin in finales if desde not in inicios or fin > desde
        ]
        self.fields["hora_hasta"].widget.attrs["data-finales-habilitados"] = ",".join(finales)

    def clean(self):
        datos = super().clean()
        seleccion = datos.get("seleccion_canchas")
        if seleccion == "todas":
            datos["canchas"] = self.fields["canchas"].queryset.all()
        if seleccion and not datos.get("canchas"):
            self.add_error("canchas", "Elegí al menos una cancha.")
        if datos.get("horario") == "dia":
            datos["hora_hasta"] = ""
        if datos.get("operacion") == "bloquear":
            if not datos.get("motivo_bloqueo"):
                self.add_error("motivo_bloqueo", "Elegí el motivo de los bloqueos.")
            datos["motivo_anulacion"] = dict(Bloqueo.Motivo.choices).get(datos.get("motivo_bloqueo"), "")
            datos["excluir_bloqueos"] = False
        else:
            datos["motivo_bloqueo"] = ""
            datos["observaciones"] = ""
        return datos

    def validar_motivos(self, previa):
        if self.cleaned_data["operacion"] == "bloquear":
            return not self.errors
        motivo = self.cleaned_data["motivo_anulacion"]
        if previa["anulaciones"] and not motivo:
            self.add_error("motivo_anulacion", "Indicá el motivo de la anulación.")
        elif previa["anulaciones"] and len(motivo) < 5:
            self.add_error("motivo_anulacion", "El motivo de anulación debe tener al menos 5 caracteres.")
        return not self.errors

    def parametros(self):
        datos = self.cleaned_data
        return {
            "operacion": datos["operacion"],
            "canchas": sorted(cancha.pk for cancha in datos["canchas"]),
            "alcance": "dia" if datos["horario"] == "dia" else "desde",
            "hora_desde": "" if datos["horario"] == "dia" else datos["horario"],
            "hora_hasta": datos["hora_hasta"],
            "excluir_clases_manuales": datos["excluir_clases_manuales"],
            "excluir_clases_generadas": datos["excluir_clases_generadas"],
            "excluir_reservas": datos["excluir_reservas"],
            "excluir_bloqueos": datos["excluir_bloqueos"],
            "motivo_bloqueo": datos["motivo_bloqueo"],
            "motivo_anulacion": datos["motivo_anulacion"],
            "observaciones": datos["observaciones"],
        }


class AgendaMesForm(forms.Form):
    sede = forms.ModelChoiceField(
        label="Sede", queryset=Sede.objects.order_by("estado", "nombre", "pk"), empty_label=None,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    mes = forms.DateField(
        label="Mes", input_formats=["%Y-%m"],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes"].widget.choices = opciones_meses_agenda()

    def clean_mes(self):
        mes = self.cleaned_data["mes"].replace(day=1)
        if mes.strftime("%Y-%m") not in dict(opciones_meses_agenda()):
            raise forms.ValidationError("Elegí un mes completo dentro del calendario operativo.")
        return mes


class AgendaOperacionMesForm(AgendaOperacionForm):
    def __init__(self, *args, sede, fecha, **kwargs):
        super().__init__(*args, sede=sede, fecha=fecha, **kwargs)
        self.fields["operacion"].choices = (("liberar", "Anular y liberar"),)
        self.fields["operacion"].initial = "liberar"
        self.fields["operacion"].disabled = True
        self.fields.pop("motivo_bloqueo")
        self.fields.pop("observaciones")
        horas = set()
        for horario in sede.horarios.all():
            franjas = [(horario.hora_inicio_1, horario.hora_fin_1)]
            if horario.hora_inicio_2 is not None:
                franjas.append((horario.hora_inicio_2, horario.hora_fin_2))
            horas.update(
                hora for hora in range(23)
                if any(time(hora) >= inicio and time(hora + 1) <= fin for inicio, fin in franjas)
            )
        self.fields["horario"].choices = [("dia", "Día completo")] + [
            (f"{hora:02d}:00", f"Desde las {hora:02d}:00") for hora in sorted(horas)
        ]
        finales = [f"{hora + 1:02d}:00" for hora in sorted(horas)]
        desde = self.data.get("horario", "dia")
        self.fields["hora_hasta"].choices = [("", "Fin del día")] + [
            (fin, fin) for fin in finales if desde == "dia" or fin > desde
        ]
        self.fields["hora_hasta"].widget.attrs["data-finales-habilitados"] = ",".join(finales)
