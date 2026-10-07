from datetime import time
from decimal import Decimal

from django import forms

from .models import Cancha, Sede, SedeHorario


class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ("nombre", "direccion", "observaciones")
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
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Información adicional sobre la sede",
                }
            ),
        }


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
        widgets = {
            "precio_reserva_vigente": forms.TextInput(
                attrs={"class": "form-control", "inputmode": "decimal", "autofocus": True}
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
                    "rows": 4,
                    "placeholder": "Información adicional sobre la cancha",
                }
            ),
        }

    def __init__(self, *args, sede, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)

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
