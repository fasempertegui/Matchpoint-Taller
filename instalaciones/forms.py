from copy import copy
from datetime import time
from decimal import Decimal

import phonenumbers
from django import forms

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_feriados

from .models import Cancha, Sede, SedeHorario, SedeHorarioEspecial


TIPOS_TELEFONO_SEDE = (
    phonenumbers.PhoneNumberType.FIXED_LINE,
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
)


def validar_telefono_sede_ar(valor):
    valor = (valor or "").strip()
    if not valor:
        return ""
    try:
        numero = phonenumbers.parse(valor, "AR")
    except phonenumbers.NumberParseException:
        raise forms.ValidationError("El formato del teléfono no es válido.")

    if numero.country_code != 54:
        raise forms.ValidationError("El teléfono debe ser argentino.")

    if (
        not phonenumbers.is_valid_number(numero)
        or phonenumbers.number_type(numero) not in TIPOS_TELEFONO_SEDE
    ):
        raise forms.ValidationError(
            "Ingresá un teléfono fijo o móvil argentino válido con código de área."
        )

    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


class SedeForm(forms.ModelForm):
    campos_servicios = (
        "tiene_estacionamiento",
        "tiene_sanitarios",
        "tiene_vestuarios",
        "tiene_wifi",
        "tiene_buffet",
    )
    campos_contacto = ("telefono_contacto_1", "telefono_contacto_2")

    class Meta:
        model = Sede
        fields = (
            "nombre",
            "direccion",
            "tiene_estacionamiento",
            "tiene_sanitarios",
            "tiene_vestuarios",
            "tiene_wifi",
            "tiene_buffet",
            "telefono_contacto_1",
            "telefono_contacto_2",
            "observaciones",
        )
        labels = {
            "direccion": "Dirección",
            "telefono_contacto_1": "Teléfono principal",
            "telefono_contacto_2": "Teléfono adicional",
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Club Norte",
                    "autofocus": True,
                }
            ),
            "direccion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Avenida Sarmiento 320",
                }
            ),
            "telefono_contacto_1": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": "387 421-2345",
                }
            ),
            "telefono_contacto_2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": "387 15 500-1220",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Información adicional sobre la sede",
                }
            ),
        }

    def clean_telefono_contacto_1(self):
        return validar_telefono_sede_ar(self.cleaned_data.get("telefono_contacto_1", ""))

    def clean_telefono_contacto_2(self):
        return validar_telefono_sede_ar(self.cleaned_data.get("telefono_contacto_2", ""))

    def campos_de_servicios(self):
        return [self[nombre] for nombre in self.campos_servicios]

    def campos_de_contacto(self):
        return [self[nombre] for nombre in self.campos_contacto]

    def cantidad_servicios_seleccionados(self):
        return sum(1 for campo in self.campos_de_servicios() if bool(campo.value()))

    def cantidad_telefonos_informados(self):
        return sum(1 for campo in self.campos_de_contacto() if str(campo.value() or "").strip())

    def abrir_servicios(self):
        if any(campo.errors for campo in self.campos_de_servicios()):
            return True
        return self.is_bound and self.cantidad_servicios_seleccionados() > 0

    def abrir_contacto(self):
        if any(campo.errors for campo in self.campos_de_contacto()):
            return True
        return self.is_bound and self.cantidad_telefonos_informados() > 0


class SedePrecioForm(forms.ModelForm):
    precio_mostrado = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Sede
        fields = ("precio_reserva_vigente",)
        localized_fields = ("precio_reserva_vigente",)
        labels = {"precio_reserva_vigente": "Establecé el nuevo precio"}
        widgets = {
            "precio_reserva_vigente": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "decimal", "autofocus": True, "placeholder": "Pesos argentinos"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["precio_reserva_vigente"].required = True
        self.fields["precio_mostrado"].initial = self.instance.precio_reserva_vigente


class CanchaForm(forms.ModelForm):
    class Meta:
        model = Cancha
        fields = ("nombre", "superficie", "observaciones")
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Cancha 1",
                    "autofocus": True,
                }
            ),
            "superficie": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Información adicional sobre la cancha",
                }
            ),
        }

    def __init__(self, *args, sede, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)
        self.fields["superficie"].choices = [
            ("", "Seleccioná una superficie"),
            *Cancha.Superficie.choices,
        ]

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        canchas_con_mismo_nombre = Cancha.objects.filter(
            sede=self.sede, nombre__iexact=nombre
        )

        if self.instance.pk:
            canchas_con_mismo_nombre = canchas_con_mismo_nombre.exclude(
                pk=self.instance.pk
            )

        if canchas_con_mismo_nombre.exists():
            raise forms.ValidationError(
                "Ya existe una cancha con ese nombre en esta sede."
            )

        return nombre

    def save(self, commit=True):
        cancha = super().save(commit=False)
        cancha.sede = self.sede
        if commit:
            cancha.save()
        return cancha


class SedeHorarioForm(forms.Form):
    dias = forms.TypedMultipleChoiceField(
        label="Días",
        choices=SedeHorario.DiaSemana.choices,
        coerce=int,
        widget=forms.CheckboxSelectMultiple(),
        error_messages={"required": "Seleccioná al menos un día."},
    )
    hora_inicio_1 = forms.IntegerField(label="Inicio de la primera franja", min_value=0, max_value=23, required=False)
    hora_fin_1 = forms.IntegerField(label="Fin de la primera franja", min_value=0, max_value=23, required=False)
    segunda_franja = forms.BooleanField(label="Segunda franja", required=False)
    hora_inicio_2 = forms.IntegerField(label="Inicio de la segunda franja", min_value=0, max_value=23, required=False)
    hora_fin_2 = forms.IntegerField(label="Fin de la segunda franja", min_value=0, max_value=23, required=False)
    accion = forms.ChoiceField(choices=(("aplicar", "Aplicar horarios"), ("cerrar", "Sin funcionamiento")))

    campos_horarios = ("hora_inicio_1", "hora_fin_1", "hora_inicio_2", "hora_fin_2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in self.campos_horarios:
            self.fields[nombre].widget = forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "max": 23, "step": 1, "inputmode": "numeric"},
            )
        if self.is_bound:
            self.data = self.data.copy()
            if self.data.get("accion") == "cerrar":
                campos_ignorados = self.campos_horarios
            elif not self.fields["segunda_franja"].to_python(self.data.get("segunda_franja")):
                campos_ignorados = self.campos_horarios[2:]
            else:
                campos_ignorados = ()
            for nombre in campos_ignorados:
                self.data.pop(nombre, None)

    def clean(self):
        datos = super().clean()
        if datos.get("accion") != "aplicar":
            return datos

        campos_requeridos = self.campos_horarios if datos.get("segunda_franja") else self.campos_horarios[:2]
        for nombre in campos_requeridos:
            if nombre not in self.errors and datos.get(nombre) is None:
                self.add_error(nombre, "Ingresá una hora entre 0 y 23.")
        if any(nombre in self.errors for nombre in self.campos_horarios):
            return datos

        horas = {
            nombre: time(datos[nombre]) if datos.get(nombre) is not None else None
            for nombre in self.campos_horarios
        }
        horario = SedeHorario(**horas)
        try:
            horario.clean()
        except forms.ValidationError as error:
            for nombre, errores in error.message_dict.items():
                self.add_error(nombre, errores)
        else:
            datos["horas"] = horas
        return datos


class SedeHorarioEspecialForm(forms.Form):
    sede = forms.ModelChoiceField(
        label="Sede",
        queryset=Sede.objects.order_by("estado", "nombre", "pk"),
        empty_label="Elegí una sede",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    fecha = forms.DateField(
        label="Fecha",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "class": "form-control",
                "type": "date",
                "min": FECHA_INICIO_OPERACIONES.isoformat(),
            },
        ),
    )
    motivo = forms.CharField(
        label="Motivo",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Mantenimiento, torneo o jornada reducida",
            }
        ),
    )
    cerrada = forms.BooleanField(label="Sede cerrada todo el día", required=False)
    hora_inicio_1 = forms.IntegerField(label="Inicio de la primera franja", min_value=0, max_value=23, required=False)
    hora_fin_1 = forms.IntegerField(label="Fin de la primera franja", min_value=0, max_value=23, required=False)
    segunda_franja = forms.BooleanField(label="Segunda franja", required=False)
    hora_inicio_2 = forms.IntegerField(label="Inicio de la segunda franja", min_value=0, max_value=23, required=False)
    hora_fin_2 = forms.IntegerField(label="Fin de la segunda franja", min_value=0, max_value=23, required=False)

    campos_horarios = ("hora_inicio_1", "hora_fin_1", "hora_inicio_2", "hora_fin_2")

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        initial = dict(kwargs.pop("initial", None) or {})
        if instance is not None:
            initial.setdefault("sede", instance.sede_id)
            initial.setdefault("fecha", instance.fecha)
            initial.setdefault("motivo", instance.motivo)
            initial.setdefault("cerrada", instance.cerrada)
            for nombre in self.campos_horarios:
                hora = getattr(instance, nombre)
                initial.setdefault(nombre, hora.hour if hora is not None else None)
            initial.setdefault("segunda_franja", instance.hora_inicio_2 is not None)
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["fecha"].widget.attrs["max"] = fecha_maxima_feriados().isoformat()
        for nombre in self.campos_horarios:
            self.fields[nombre].widget = forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "max": 23, "step": 1, "inputmode": "numeric"},
            )
        if instance is not None and instance.pk is not None:
            self.fields["sede"].disabled = True
            self.fields["fecha"].disabled = True
        if self.is_bound:
            self.data = self.data.copy()
            if self.fields["cerrada"].to_python(self.data.get("cerrada")):
                campos_ignorados = (*self.campos_horarios, "segunda_franja")
            elif not self.fields["segunda_franja"].to_python(self.data.get("segunda_franja")):
                campos_ignorados = self.campos_horarios[2:]
            else:
                campos_ignorados = ()
            for nombre in campos_ignorados:
                self.data.pop(nombre, None)

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if not motivo:
            raise forms.ValidationError("Indicá el motivo del horario especial.")
        return motivo

    def clean(self):
        datos = super().clean()
        cerrada = bool(datos.get("cerrada"))
        if not cerrada:
            campos_requeridos = self.campos_horarios if datos.get("segunda_franja") else self.campos_horarios[:2]
            for nombre in campos_requeridos:
                if nombre not in self.errors and datos.get(nombre) is None:
                    self.add_error(nombre, "Ingresá una hora entre 0 y 23.")
        if self.errors:
            return datos

        horas = {
            nombre: (
                None
                if cerrada or datos.get(nombre) is None
                else time(datos[nombre])
            )
            for nombre in self.campos_horarios
        }
        horario = copy(self.instance) if self.instance is not None else SedeHorarioEspecial()
        horario.sede = datos["sede"]
        horario.fecha = datos["fecha"]
        horario.motivo = datos["motivo"]
        horario.cerrada = cerrada
        for nombre, hora in horas.items():
            setattr(horario, nombre, hora)
        try:
            horario.clean()
        except forms.ValidationError as error:
            for nombre, errores in error.message_dict.items():
                self.add_error(nombre if nombre in self.fields else None, errores)
        else:
            datos["horario"] = horario
        return datos
