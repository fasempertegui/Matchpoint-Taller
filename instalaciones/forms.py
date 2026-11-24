from copy import copy
from datetime import time
from decimal import Decimal

import phonenumbers
from django import forms
from django.core.exceptions import ValidationError

from common.fechas import FECHA_INICIO_OPERACIONES, fecha_maxima_feriados

from .direcciones import (
    CORREO_ARGENTINO_CPA_URL,
    LOCALIDAD_CHOICES,
    PROVINCIA_NOMBRE,
    componer_direccion,
    crear_token_formulario_direccion,
    etiqueta_localidad,
    validar_altura,
    validar_calle,
    validar_cpa,
    validar_localidad_codigo,
    validar_seleccion_georef,
    validar_token_formulario_direccion,
)
from .models import Cancha, Sede, SedeHorario, SedeHorarioEspecial
from .ubicacion import (
    centros_localidades,
    punto_en_localidad,
    validar_par_coordenadas,
)


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
    campos_direccion = (
        "direccion_formulario_token",
        "direccion_modo",
        "direccion_seleccion_token",
        "direccion_consulta",
        "localidad_codigo",
        "calle",
        "altura",
        "cpa",
        "confirmacion_direccion_manual",
    )
    campos_ubicacion = (
        "ubicacion_modo",
        "latitud_entrada",
        "longitud_entrada",
    )

    direccion_formulario_token = forms.CharField(required=False, widget=forms.HiddenInput())
    direccion_modo = forms.CharField(required=False, widget=forms.HiddenInput())
    direccion_seleccion_token = forms.CharField(required=False, widget=forms.HiddenInput())
    ubicacion_modo = forms.CharField(required=False, widget=forms.HiddenInput())
    latitud_entrada = forms.CharField(
        label="Latitud",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "decimal",
                "placeholder": "-24.781872",
                "autocomplete": "off",
            }
        ),
    )
    longitud_entrada = forms.CharField(
        label="Longitud",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "decimal",
                "placeholder": "-65.411627",
                "autocomplete": "off",
            }
        ),
    )
    direccion_consulta = forms.CharField(
        label="Buscar calle y altura",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej.: Balcarce 643",
                "autocomplete": "off",
            }
        ),
    )
    localidad_codigo = forms.ChoiceField(
        label="Localidad",
        choices=(("", "Seleccioná una localidad"), *LOCALIDAD_CHOICES),
        required=False,
        error_messages={"invalid_choice": "Seleccioná una localidad habilitada de Salta."},
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    calle = forms.CharField(
        label="Calle o ruta",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej.: Balcarce o Ruta Nacional 9",
            }
        ),
    )
    altura = forms.CharField(
        label="Altura",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej.: 643, 643 B, Km 12 o s/n",
            }
        ),
    )
    cpa = forms.CharField(
        label="CPA (opcional)",
        max_length=8,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej.: A4400BKM",
                "maxlength": "8",
                "autocapitalize": "characters",
            }
        ),
    )
    confirmacion_direccion_manual = forms.BooleanField(
        label="Confirmo que verifiqué la calle y altura con la sede o una fuente oficial.",
        required=False,
    )

    class Meta:
        model = Sede
        fields = (
            "nombre",
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

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        instance = kwargs.get("instance")
        self.es_edicion = bool(instance and instance.pk)
        self.alcance_direccion = "editar" if self.es_edicion else "crear"
        self.sede_id_direccion = instance.pk if self.es_edicion else None
        self.provincia_nombre = PROVINCIA_NOMBRE
        self.correo_argentino_cpa_url = CORREO_ARGENTINO_CPA_URL

        initial = dict(kwargs.pop("initial", None) or {})
        initial.setdefault(
            "direccion_formulario_token",
            crear_token_formulario_direccion(
                usuario_id=usuario.pk,
                alcance=self.alcance_direccion,
                sede_id=self.sede_id_direccion,
            ),
        )
        initial.setdefault("direccion_modo", "mantener" if self.es_edicion else "")
        initial.setdefault("ubicacion_modo", "mantener" if self.es_edicion else "")
        if self.es_edicion:
            initial.setdefault("localidad_codigo", instance.localidad_codigo)
            initial.setdefault("calle", instance.calle)
            initial.setdefault("altura", instance.altura)
            initial.setdefault("cpa", instance.cpa)
            initial.setdefault(
                "confirmacion_direccion_manual",
                not bool(instance.calle_georef_id),
            )
            initial.setdefault("latitud_entrada", f"{instance.latitud:.6f}")
            initial.setdefault("longitud_entrada", f"{instance.longitud:.6f}")
        super().__init__(*args, initial=initial, **kwargs)
        self._token_formulario_renovado = None

    def clean_telefono_contacto_1(self):
        return validar_telefono_sede_ar(self.cleaned_data.get("telefono_contacto_1", ""))

    def clean_telefono_contacto_2(self):
        return validar_telefono_sede_ar(self.cleaned_data.get("telefono_contacto_2", ""))

    def _agregar_error_validacion(self, campo, error):
        for mensaje in error.messages:
            self.add_error(campo, mensaje)

    def _limpiar_direccion(self, datos):
        modo = (datos.get("direccion_modo") or "").strip()

        if modo == "mantener":
            if self.es_edicion:
                datos["direccion_cambio"] = False
                return
            self.add_error("direccion_consulta", "Cargá la dirección estructurada de la sede.")
            return

        if modo == "":
            self.add_error("direccion_consulta", "Cargá la dirección estructurada de la sede.")
            return

        if modo not in ("georef", "manual", "editar_existente"):
            self.add_error("direccion_consulta", "Indicá cómo querés cargar la dirección de la sede.")
            return

        if modo == "editar_existente" and not self.es_edicion:
            self.add_error("direccion_consulta", "Cargá la dirección estructurada de la sede.")
            return

        localidad_codigo = ""
        if "localidad_codigo" not in self.errors:
            try:
                localidad_codigo = validar_localidad_codigo(datos.get("localidad_codigo"))
            except ValidationError as error:
                self._agregar_error_validacion("localidad_codigo", error)

        altura = ""
        try:
            altura = validar_altura(datos.get("altura"))
        except ValidationError as error:
            self._agregar_error_validacion("altura", error)

        cpa = ""
        try:
            cpa = validar_cpa(datos.get("cpa"))
        except ValidationError as error:
            self._agregar_error_validacion("cpa", error)

        calle = ""
        calle_georef_id = ""

        if modo == "georef":
            try:
                contexto_form = validar_token_formulario_direccion(
                    datos.get("direccion_formulario_token"),
                    usuario_id=self.usuario.pk,
                    alcance=self.alcance_direccion,
                    sede_id=self.sede_id_direccion,
                )
            except ValidationError as error:
                self._token_formulario_renovado = crear_token_formulario_direccion(
                    usuario_id=self.usuario.pk,
                    alcance=self.alcance_direccion,
                    sede_id=self.sede_id_direccion,
                )
                self._agregar_error_validacion("direccion_consulta", error)
                return

            if localidad_codigo:
                try:
                    seleccion = validar_seleccion_georef(
                        datos.get("direccion_seleccion_token"),
                        usuario_id=self.usuario.pk,
                        alcance=self.alcance_direccion,
                        sede_id=self.sede_id_direccion,
                        formulario_nonce=contexto_form["nonce"],
                        localidad_codigo=localidad_codigo,
                    )
                except ValidationError as error:
                    self._agregar_error_validacion("direccion_consulta", error)
                else:
                    localidad_codigo = seleccion["localidad_codigo"]
                    calle = seleccion["calle"]
                    calle_georef_id = seleccion["calle_georef_id"]

        elif modo == "manual":
            try:
                calle = validar_calle(datos.get("calle"))
            except ValidationError as error:
                self._agregar_error_validacion("calle", error)
            if not datos.get("confirmacion_direccion_manual"):
                self.add_error(
                    "confirmacion_direccion_manual",
                    "Confirmá que verificaste la calle y altura con la sede o una fuente oficial.",
                )

        elif modo == "editar_existente":
            try:
                calle = validar_calle(datos.get("calle") or self.instance.calle)
            except ValidationError as error:
                self._agregar_error_validacion("calle", error)
            misma_calle = (
                localidad_codigo == self.instance.localidad_codigo
                and calle == self.instance.calle
            )
            if misma_calle:
                calle_georef_id = self.instance.calle_georef_id
            else:
                if not datos.get("confirmacion_direccion_manual"):
                    self.add_error(
                        "confirmacion_direccion_manual",
                        "Al modificar la calle o localidad manualmente, confirmá que verificaste el domicilio o buscá en Georef.",
                    )
                calle_georef_id = ""

        if any(campo in self.errors for campo in self.campos_direccion):
            return

        datos["direccion_cambio"] = True
        datos["direccion_estructurada"] = {
            "localidad_codigo": localidad_codigo,
            "calle": calle,
            "altura": altura,
            "cpa": cpa,
            "calle_georef_id": calle_georef_id,
        }

    def _limpiar_ubicacion(self, datos):
        modo_ubicacion = (datos.get("ubicacion_modo") or "").strip()
        lat_raw = (datos.get("latitud_entrada") or "").strip()
        lon_raw = (datos.get("longitud_entrada") or "").strip()

        if modo_ubicacion == "mantener" and self.es_edicion:
            latitud = self.instance.latitud
            longitud = self.instance.longitud
            ubicacion_cambio = False
        elif modo_ubicacion in ("", "marcar"):
            if not lat_raw and not lon_raw:
                self.add_error(
                    "latitud_entrada",
                    "Marcá la ubicación de entrada de la sede en el mapa o ingresá sus coordenadas.",
                )
                return
            try:
                latitud, longitud = validar_par_coordenadas(lat_raw, lon_raw)
            except ValidationError as error:
                for campo, mensajes in error.message_dict.items():
                    self.add_error(campo, mensajes)
                return
            ubicacion_cambio = True
        else:
            self.add_error(
                "latitud_entrada",
                "Marcá una ubicación de entrada válida en el mapa o ingresá sus coordenadas.",
            )
            return

        if datos.get("direccion_cambio"):
            localidad_efectiva = datos["direccion_estructurada"]["localidad_codigo"]
        elif (datos.get("localidad_codigo") or "").strip() in centros_localidades():
            localidad_efectiva = (datos.get("localidad_codigo") or "").strip()
        elif self.es_edicion:
            localidad_efectiva = self.instance.localidad_codigo
        else:
            localidad_efectiva = ""

        cambio_localidad = (
            self.es_edicion
            and bool(localidad_efectiva)
            and localidad_efectiva != self.instance.localidad_codigo
        )

        if not localidad_efectiva:
            self.add_error(
                "latitud_entrada",
                "Cargá primero una dirección con localidad habilitada para validar el pin de entrada.",
            )
            return
        if not punto_en_localidad(localidad_efectiva, latitud, longitud):
            nombre_localidad = etiqueta_localidad(localidad_efectiva)
            if cambio_localidad and not ubicacion_cambio:
                mensaje = (
                    f"El pin guardado quedó fuera de {nombre_localidad}. "
                    "Marcá nuevamente la entrada dentro de esa localidad."
                )
            else:
                mensaje = (
                    f"El pin debe quedar dentro de {nombre_localidad} (incluido su borde)."
                )
            self.add_error("latitud_entrada", mensaje)
            return

        datos["ubicacion_cambio"] = ubicacion_cambio
        datos["ubicacion_pin"] = {
            "latitud": latitud,
            "longitud": longitud,
        }

    def clean(self):
        datos = super().clean()
        self._limpiar_direccion(datos)
        self._limpiar_ubicacion(datos)
        return datos

    def save(self, commit=True):
        sede = super().save(commit=False)
        if self.cleaned_data.get("direccion_cambio"):
            for campo, valor in self.cleaned_data["direccion_estructurada"].items():
                setattr(sede, campo, valor)
        if self.cleaned_data.get("ubicacion_cambio"):
            for campo, valor in self.cleaned_data["ubicacion_pin"].items():
                setattr(sede, campo, valor)
        if commit:
            sede.save()
        return sede

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

    def abrir_direccion(self):
        return any(self[nombre].errors for nombre in self.campos_direccion)

    def abrir_ubicacion(self):
        return any(self[nombre].errors for nombre in self.campos_ubicacion)

    @property
    def ubicacion_modo_actual(self):
        return (self["ubicacion_modo"].value() or "").strip()

    @property
    def tiene_ubicacion_actual(self):
        modo = self.ubicacion_modo_actual
        if modo == "mantener" and self.es_edicion:
            return True
        return bool(
            (self["latitud_entrada"].value() or "").strip()
            and (self["longitud_entrada"].value() or "").strip()
        )

    @property
    def ubicacion_resumen_actual(self):
        modo = self.ubicacion_modo_actual
        if modo == "mantener" and self.es_edicion:
            return f"Lat {self.instance.latitud:.6f}, Lon {self.instance.longitud:.6f}"
        lat = (self["latitud_entrada"].value() or "").strip()
        lon = (self["longitud_entrada"].value() or "").strip()
        if lat and lon:
            return f"Lat {lat}, Lon {lon}"
        return ""

    @property
    def token_formulario_direccion_actual(self):
        if self._token_formulario_renovado:
            return self._token_formulario_renovado
        return self["direccion_formulario_token"].value() or ""

    @property
    def direccion_modo_actual(self):
        return (self["direccion_modo"].value() or "").strip()

    @property
    def es_modo_manual(self):
        return self.direccion_modo_actual == "manual"

    @property
    def tiene_direccion_estructurada_actual(self):
        modo = self.direccion_modo_actual
        if modo == "mantener":
            return self.es_edicion
        return bool(
            (self["localidad_codigo"].value() or "").strip()
            and (self["calle"].value() or "").strip()
            and (self["altura"].value() or "").strip()
        )

    @property
    def direccion_resumen_actual(self):
        modo = self.direccion_modo_actual
        if modo == "mantener" and self.es_edicion:
            return self.instance.direccion_completa
        compuesta = componer_direccion(
            self["calle"].value() or "",
            self["altura"].value() or "",
            self["localidad_codigo"].value() or "",
            self["cpa"].value() or "",
        )
        if compuesta:
            return compuesta
        if self.es_edicion:
            return self.instance.direccion_completa
        return ""

    @property
    def direccion_origen_actual(self):
        modo = self.direccion_modo_actual
        if modo == "mantener" and self.es_edicion:
            return self.instance.origen_calle_display
        if modo == "georef" and (self["direccion_seleccion_token"].value() or "").strip():
            return "Normalizada con Georef"
        if modo == "manual" and self.tiene_direccion_estructurada_actual:
            return "Carga manual confirmada"
        if modo == "editar_existente" and self.es_edicion:
            return self.instance.origen_calle_display
        return ""


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
