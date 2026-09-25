import re
import secrets
import string
import unicodedata

import phonenumbers
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from common.fechas import fecha_minima_nacimiento, validar_fecha_nacimiento

from .models import Rol, Usuario, UsuarioRol


class InicioSesionForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "El usuario o la contraseña no son correctos.",
        "inactive": "Tu cuenta está inactiva. Contactá a un administrador.",
    }

    def get_invalid_login_error(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            try:
                usuario = Usuario._default_manager.get_by_natural_key(username)
            except Usuario.DoesNotExist:
                pass
            else:
                if not usuario.is_active and usuario.check_password(password):
                    return forms.ValidationError(
                        self.error_messages["inactive"], code="inactive"
                    )
        return super().get_invalid_login_error()


def _normalizar_para_usuario(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", texto.lower())


def validar_nombre_sin_numeros(valor):
    if any(caracter.isnumeric() for caracter in valor):
        raise forms.ValidationError("No se permiten números.")


def validar_email_disponible(email, *, excluir_usuario=None):
    usuarios = Usuario.objects.filter(email__iexact=email)
    if excluir_usuario and excluir_usuario.pk:
        usuarios = usuarios.exclude(pk=excluir_usuario.pk)
    if usuarios.exists():
        raise forms.ValidationError("Ya existe un usuario registrado con ese email.")
    return email


def generar_nombre_usuario(nombre, apellido):
    validar_nombre_sin_numeros(nombre)
    validar_nombre_sin_numeros(apellido)
    base = _normalizar_para_usuario(apellido)
    inicial = _normalizar_para_usuario(nombre)[:1]
    if not base or not inicial:
        raise forms.ValidationError(
            "Ingresá un nombre y un apellido con letras para generar el usuario."
        )
    candidato = f"{base}{inicial}"
    sufijo = 1
    resultado = candidato
    while Usuario.objects.filter(username__iexact=resultado).exists():
        resultado = f"{candidato}{sufijo}"
        sufijo += 1
    return resultado


def crear_usuario_con_nombre_generado(nombre, apellido, **datos):
    while True:
        nombre_usuario = generar_nombre_usuario(nombre, apellido)
        try:
            with transaction.atomic():
                return Usuario.objects.create_user(
                    username=nombre_usuario,
                    first_name=nombre,
                    last_name=apellido,
                    **datos,
                )
        except IntegrityError:
            # Si otra alta ocupó el nombre, se busca el siguiente sufijo disponible.
            if not Usuario.objects.filter(username__iexact=nombre_usuario).exists():
                raise


class NombreUsuarioAutomaticoMixin:
    def clean_nombre_usuario(self):
        nombre = self.cleaned_data.get("nombre")
        apellido = self.cleaned_data.get("apellido")
        if nombre and apellido:
            return generar_nombre_usuario(nombre, apellido)
        return ""


def generar_contrasena():
    """Genera una contraseña alfanumérica aleatoria."""
    return "".join(
        (
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            *(secrets.choice(string.ascii_letters + string.digits) for _ in range(9)),
        )
    )


def generar_contrasena_valida(usuario):
    while True:
        contrasena = generar_contrasena()
        try:
            validate_password(contrasena, usuario)
        except forms.ValidationError:
            continue
        return contrasena


def validar_celular_ar(valor):
    try:
        numero = phonenumbers.parse(valor, "AR")
    except phonenumbers.NumberParseException:
        raise forms.ValidationError("El formato del celular no es válido.")

    if numero.country_code != 54:
        raise forms.ValidationError("El celular debe ser argentino.")

    if (
        phonenumbers.is_valid_number(numero)
        and phonenumbers.number_type(numero) == phonenumbers.PhoneNumberType.MOBILE
    ):
        return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)

    # El campo es exclusivamente para celulares. Si se ingresó el número
    # nacional sin 9 ni 15, se agrega el indicador móvil argentino antes de
    # validarlo y guardarlo en formato internacional.
    numero_nacional = phonenumbers.national_significant_number(numero)
    try:
        numero = phonenumbers.parse(f"+549{numero_nacional}", None)
    except phonenumbers.NumberParseException:
        raise forms.ValidationError("El número de celular no es válido.")

    if (
        not phonenumbers.is_valid_number(numero)
        or phonenumbers.number_type(numero) != phonenumbers.PhoneNumberType.MOBILE
    ):
        raise forms.ValidationError("El número de celular no es válido.")

    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


class UsuarioRegistroForm(NombreUsuarioAutomaticoMixin, forms.Form):
    nombre = forms.CharField(
        max_length=100,
        validators=[validar_nombre_sin_numeros],
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    apellido = forms.CharField(
        max_length=100,
        validators=[validar_nombre_sin_numeros],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    celular_contacto = forms.CharField(
        label="Celular",
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ej.: +54 387 555-1234"}
        ),
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        validators=[validar_fecha_nacimiento],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"class": "form-control", "type": "date"},
        ),
    )
    nombre_usuario = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contrasena = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    confirmar_contrasena = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_nacimiento"].widget.attrs.update(
            min=fecha_minima_nacimiento().isoformat(), max=timezone.localdate().isoformat()
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        return validar_email_disponible(email)

    def clean_celular_contacto(self):
        return validar_celular_ar(self.cleaned_data["celular_contacto"])

    def clean(self):
        datos = super().clean()
        contrasena = datos.get("contrasena")
        confirmar_contrasena = datos.get("confirmar_contrasena")
        if contrasena and confirmar_contrasena and contrasena != confirmar_contrasena:
            self.add_error("confirmar_contrasena", "Las contraseñas no coinciden.")
        if contrasena:
            candidato = Usuario(
                username=datos.get("nombre_usuario", ""),
                email=datos.get("email", ""),
                first_name=datos.get("nombre", ""),
                last_name=datos.get("apellido", ""),
            )
            try:
                validate_password(contrasena, candidato)
            except forms.ValidationError as error:
                self.add_error("contrasena", error)
        return datos

    def guardar(self):
        with transaction.atomic():
            return crear_usuario_con_nombre_generado(
                self.cleaned_data["nombre"],
                self.cleaned_data["apellido"],
                email=self.cleaned_data["email"],
                password=self.cleaned_data["contrasena"],
                celular_contacto=self.cleaned_data["celular_contacto"],
                fecha_nacimiento=self.cleaned_data.get("fecha_nacimiento"),
                debe_cambiar_contrasena=False,
            )


class UsuarioCrearForm(NombreUsuarioAutomaticoMixin, forms.Form):
    nombre = forms.CharField(
        max_length=100,
        validators=[validar_nombre_sin_numeros],
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    apellido = forms.CharField(
        max_length=100,
        validators=[validar_nombre_sin_numeros],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    celular_contacto = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ej.: +54 387 555-1234"}
        ),
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        validators=[validar_fecha_nacimiento],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"class": "form-control", "type": "date"},
        ),
    )
    nombre_usuario = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contrasena = forms.CharField(
        label="Contraseña",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Se muestra una sola vez: comunicásela a la persona.",
    )
    rol_profesor = forms.BooleanField(required=False, label="Profesor")
    rol_alumno = forms.BooleanField(required=False, label="Alumno")
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_nacimiento"].widget.attrs.update(
            min=fecha_minima_nacimiento().isoformat(), max=timezone.localdate().isoformat()
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        return validar_email_disponible(email)

    def clean_celular_contacto(self):
        return validar_celular_ar(self.cleaned_data["celular_contacto"])

    def clean_contrasena(self):
        contrasena = self.cleaned_data["contrasena"]
        candidato = Usuario(
            username=self.cleaned_data.get("nombre_usuario", ""),
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data.get("nombre", ""),
            last_name=self.cleaned_data.get("apellido", ""),
        )
        validate_password(contrasena, candidato)
        return contrasena

    def guardar(self, *, exigir_cambio_contrasena=True, es_superusuario=False):
        with transaction.atomic():
            usuario = crear_usuario_con_nombre_generado(
                self.cleaned_data["nombre"],
                self.cleaned_data["apellido"],
                email=self.cleaned_data["email"],
                password=self.cleaned_data["contrasena"],
                celular_contacto=self.cleaned_data["celular_contacto"],
                fecha_nacimiento=self.cleaned_data.get("fecha_nacimiento"),
                observaciones=self.cleaned_data.get("observaciones", ""),
                debe_cambiar_contrasena=exigir_cambio_contrasena,
                is_superuser=es_superusuario,
            )
            if self.cleaned_data.get("rol_profesor"):
                UsuarioRol.objects.create(usuario=usuario, rol=Rol.objects.get(codigo=Rol.PROFESOR))
            if self.cleaned_data.get("rol_alumno"):
                UsuarioRol.objects.create(usuario=usuario, rol=Rol.objects.get(codigo=Rol.ALUMNO))
        return usuario


class UsuarioEditarForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ("email",)
        labels = {"email": "Email"}
        widgets = {"email": forms.EmailInput(attrs={"class": "form-control"})}

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        return validar_email_disponible(email, excluir_usuario=self.instance)


class UsuarioBusquedaForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nombre, apellido, email o nombre de usuario",
            }
        ),
    )
    rol = forms.ModelChoiceField(
        required=False,
        queryset=Rol.objects.all(),
        to_field_name="codigo",
        empty_label="Todos los roles",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    estado = forms.ChoiceField(
        required=False,
        choices=(("", "Todos los estados"), ("activo", "Activo"), ("inactivo", "Inactivo")),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
