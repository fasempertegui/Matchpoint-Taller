import json
from calendar import monthrange
from datetime import datetime, time
from decimal import Decimal

from django import forms
from django.utils import timezone

from bloqueos.models import Bloqueo
from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_agenda, fecha_maxima_eventos, opciones_meses_agenda
from instalaciones.horarios import horario_efectivo, horarios_del_mes
from instalaciones.models import Cancha, Sede
from usuarios.models import Rol, Usuario


class CanchaAgendaField(forms.ModelChoiceField):
    def label_from_instance(self, cancha):
        return cancha.nombre


class AgendaFiltroForm(forms.Form):
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.all(),
        empty_label=None,
        widget=forms.Select(attrs={"class": "boton boton-secundario boton-chico"}),
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
        queryset=Usuario.objects.habilitados().filter(
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
        return f"{cancha.sede.nombre} · {cancha.nombre}"


class AgendaOperacionForm(forms.Form):
    operacion = forms.ChoiceField(
        label="Operación *",
        choices=(("liberar", "Anular y liberar"), ("bloquear", "Anular y bloquear")),
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="bloquear",
    )
    seleccion_sedes = forms.ChoiceField(
        label="Sedes *",
        choices=(("todas", "Todas las sedes"), ("seleccionar", "Seleccionar")),
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="todas",
    )
    sedes = forms.ModelMultipleChoiceField(
        label="Elegí las sedes *",
        queryset=Sede.objects.order_by("nombre", "pk"),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    seleccion_canchas = forms.ChoiceField(
        label="Canchas *",
        choices=(("todas", "Todas las canchas de las sedes elegidas"), ("seleccionar", "Seleccionar")),
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
    actividades = forms.MultipleChoiceField(
        label="Elegir actividades",
        choices=(
            ("clase_manual", "Clases creadas manualmente"),
            ("clase_generada", "Clases generadas desde la planilla"),
            ("reserva", "Reservas"),
            ("bloqueo", "Bloqueos"),
        ),
        required=False,
        initial=(),
        widget=forms.CheckboxSelectMultiple(),
    )
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
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, fecha, **kwargs):
        super().__init__(*args, **kwargs)
        sedes = list(self.fields["sedes"].queryset)
        self.fields["canchas"].queryset = Cancha.objects.select_related("sede").order_by("sede__nombre", "nombre", "pk")
        if fecha > fecha_maxima_eventos():
            self.fields["operacion"].choices = (("liberar", "Anular y liberar"),)
            self.fields["operacion"].initial = "liberar"
        ahora = timezone.localtime()
        horas_por_sede = {str(sede.pk): self._horas_habilitadas(sede, fecha, ahora) for sede in sedes}
        self.fields["horario"].widget.attrs["data-horas-por-sede"] = json.dumps(horas_por_sede)
        sedes_elegidas = horas_por_sede.keys()
        if self.data.get("seleccion_sedes") == "seleccionar":
            sedes_elegidas = {str(sede) for sede in self["sedes"].value() or ()}
        horas = sorted({hora for sede in sedes_elegidas for hora in horas_por_sede.get(sede, ())})
        self.fields["horario"].choices = [("dia", "Día completo")] + [
            (f"{hora:02d}:00", f"Desde las {hora:02d}:00") for hora in horas
        ]
        desde = self.data.get("horario", "dia")
        finales = [f"{hora + 1:02d}:00" for hora in horas]
        self.fields["hora_hasta"].choices = [("", "Fin del día")] + [
            (fin, fin) for fin in finales if desde == "dia" or fin > desde
        ]

    def _horas_habilitadas(self, sede, fecha, ahora):
        horario = horario_efectivo(sede, fecha)
        return [
            hora for hora in range(23)
            if timezone.make_aware(datetime.combine(fecha, time(hora))) > ahora
            and horario.contiene(time(hora), time(hora + 1))
        ]

    def clean(self):
        datos = super().clean()
        if datos.get("seleccion_sedes") == "todas":
            datos["sedes"] = self.fields["sedes"].queryset.all()
        sedes = datos.get("sedes")
        if not sedes and "sedes" not in self.errors:
            self.add_error("sedes", "Elegí al menos una sede.")
        if sedes and datos.get("seleccion_canchas") == "todas":
            datos["canchas"] = self.fields["canchas"].queryset.filter(sede__in=sedes)
        if sedes and datos.get("seleccion_canchas") and "canchas" not in self.errors:
            canchas = datos.get("canchas")
            if not canchas:
                self.add_error("canchas", "Elegí al menos una cancha en las sedes seleccionadas.")
            elif canchas.exclude(sede__in=sedes).exists():
                self.add_error("canchas", "Elegí sólo canchas de las sedes seleccionadas.")
        if datos.get("horario") == "dia":
            datos["hora_hasta"] = ""
        if datos.get("operacion") == "bloquear":
            if not datos.get("motivo_bloqueo"):
                self.add_error("motivo_bloqueo", "Elegí el motivo de los bloqueos.")
            datos["motivo_anulacion"] = dict(Bloqueo.Motivo.choices).get(datos.get("motivo_bloqueo"), "")
            datos["actividades"] = [actividad for actividad in datos.get("actividades", []) if actividad != "bloqueo"]
        else:
            datos["motivo_bloqueo"] = ""
            datos["observaciones"] = ""
            if datos.get("operacion") == "liberar" and not datos.get("actividades"):
                self.add_error("actividades", "Elegí al menos una actividad para anular.")
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
            "seleccion_sedes": datos["seleccion_sedes"],
            "sedes": sorted(sede.pk for sede in datos["sedes"]),
            "seleccion_canchas": datos["seleccion_canchas"],
            "canchas": sorted(cancha.pk for cancha in datos["canchas"]),
            "alcance": "dia" if datos["horario"] == "dia" else "desde",
            "hora_desde": "" if datos["horario"] == "dia" else datos["horario"],
            "hora_hasta": datos["hora_hasta"],
            "actividades": sorted(set(datos["actividades"])),
            "motivo_bloqueo": datos["motivo_bloqueo"],
            "motivo_anulacion": datos["motivo_anulacion"],
            "observaciones": datos["observaciones"],
        }


class AgendaMesForm(forms.Form):
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
    DIAS_SEMANA = (
        (1, "Lunes"),
        (2, "Martes"),
        (3, "Miércoles"),
        (4, "Jueves"),
        (5, "Viernes"),
        (6, "Sábado"),
        (7, "Domingo"),
    )

    fecha_desde = forms.DateField(
        label="Desde",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    fecha_hasta = forms.DateField(
        label="Hasta",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    dias_semana = forms.TypedMultipleChoiceField(
        label="Días de la semana",
        choices=DIAS_SEMANA,
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

    def __init__(self, *args, fecha, **kwargs):
        super().__init__(*args, fecha=fecha, **kwargs)
        primer_dia = fecha.replace(day=1)
        ultimo_dia = primer_dia.replace(day=monthrange(primer_dia.year, primer_dia.month)[1])
        self.fecha_minima = max(timezone.localdate(), primer_dia)
        self.fecha_maxima = ultimo_dia
        for campo in ("fecha_desde", "fecha_hasta"):
            self.fields[campo].widget.attrs.update({
                "min": self.fecha_minima.isoformat(),
                "max": self.fecha_maxima.isoformat(),
            })
        self.fields["operacion"].choices = (("liberar", "Anular y liberar"),)
        self.fields["operacion"].initial = "liberar"
        self.fields["operacion"].disabled = True
        self.fields["operacion"].widget.attrs["form"] = "agenda-operacion-mes"
        self.fields.pop("motivo_bloqueo")
        self.fields.pop("observaciones")

    def _horas_habilitadas(self, sede, fecha, ahora):
        return sorted({
            hora for horario in horarios_del_mes(sede, fecha).values()
            for inicio, fin in horario.franjas
            for hora in range(inicio.hour, fin.hour)
        })

    def clean(self):
        datos = super().clean()
        fecha_desde = datos.get("fecha_desde")
        fecha_hasta = datos.get("fecha_hasta")
        rango_error = f"Elegí una fecha entre el {self.fecha_minima:%d/%m/%Y} y el {self.fecha_maxima:%d/%m/%Y}."
        if fecha_desde and not self.fecha_minima <= fecha_desde <= self.fecha_maxima:
            self.add_error("fecha_desde", rango_error)
        if fecha_hasta and not self.fecha_minima <= fecha_hasta <= self.fecha_maxima:
            self.add_error("fecha_hasta", rango_error)
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            self.add_error("fecha_hasta", "La fecha hasta debe ser igual o posterior a la fecha desde.")
        return datos

    def parametros(self):
        datos = self.cleaned_data
        parametros = super().parametros()
        for campo in ("fecha_desde", "fecha_hasta"):
            if datos[campo]:
                parametros[campo] = datos[campo].isoformat()
        if datos["dias_semana"]:
            parametros["dias_semana"] = sorted(set(datos["dias_semana"]))
        return parametros
