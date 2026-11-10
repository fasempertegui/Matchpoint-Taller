from calendar import monthrange

from django import forms
from django.db.models import Q
from common.disponibilidad import validar_disponibilidad, validar_limite_reservas_organizadas
from common.fechas import FECHA_INICIO_OPERACIONES
from instalaciones.models import Cancha
from usuarios.models import Rol, Usuario
from .disponibilidad import validar_fecha_reserva


class ReservaAnulacionForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de anulación",
        min_length=5,
        help_text="Mínimo 5 caracteres",
        error_messages={
            "required": "Indicá el motivo de la anulación.",
            "min_length": "El motivo de anulación debe tener al menos 5 caracteres.",
        },
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class TurnoReservaForm(forms.Form):
    cancha = forms.ModelChoiceField(queryset=Cancha.objects.select_related("sede"), widget=forms.HiddenInput())
    fecha = forms.DateField(validators=[validar_fecha_reserva], widget=forms.HiddenInput())
    hora = forms.TypedChoiceField(choices=[(n, n) for n in range(23)], coerce=int, widget=forms.HiddenInput())


class OrganizadorReservaForm(forms.Form):
    organizador = forms.ModelChoiceField(queryset=Usuario.objects.none(), widget=forms.HiddenInput())

    def __init__(self, *args, fecha, hora, **kwargs):
        super().__init__(*args, **kwargs)
        self.fecha = fecha
        self.hora = hora
        self.fields["organizador"].queryset = Usuario.objects.habilitados().filter(
            roles__rol__codigo__in=(Rol.RESERVAS, Rol.ADMINISTRADOR),
        ).distinct().order_by("last_name", "first_name", "username")


    def clean(self):
        datos = super().clean()
        organizador = datos.get("organizador")
        if organizador is not None:
            try:
                validar_limite_reservas_organizadas(organizador.pk)
                validar_disponibilidad(
                    {organizador.pk}, self.fecha, self.hora,
                )
            except forms.ValidationError as error:
                if error.code == "persona_ocupada":
                    raise forms.ValidationError(
                        "Esta persona participa en otro evento a esa hora",
                        code=error.code,
                    ) from error
                raise
        return datos

class InvitadosReservaForm(forms.Form):
    invitados = forms.ModelMultipleChoiceField(
        label="Invitados", required=False, queryset=Usuario.objects.none(),
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": 8}),
        help_text="Podés seleccionar varias personas. El organizador no se incluye.",
    )
    observaciones = forms.CharField(label="Observaciones", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))

    def __init__(self, *args, organizador_id, reserva=None, **kwargs):
        super().__init__(*args, **kwargs)
        actuales = set()
        if reserva is not None:
            actuales = set(reserva.invitados.all().values_list("usuario_id", flat=True))
        self.fields["invitados"].queryset = Usuario.objects.filter(
            Q(pk__in=actuales) | Q(is_active=True, correo_verificado_en__isnull=False, roles__rol__codigo__in=(Rol.RESERVAS, Rol.ADMINISTRADOR)),
        ).filter(correo_verificado_en__isnull=False).exclude(pk=organizador_id).distinct().order_by("last_name", "first_name", "username")
        if reserva is not None:
            self.fields.pop("observaciones")


class ResultadoReservaForm(forms.Form):
    resultado = forms.ChoiceField(label="Resultado", choices=(("realizada", "Realizada"), ("no_realizada", "No realizada")), widget=forms.Select(attrs={"class": "form-control"}))
    motivo = forms.CharField(min_length=5, label="Motivo de corrección", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    version = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, reserva, **kwargs):
        super().__init__(*args, **kwargs)
        if reserva.resultado_uso == "sin_registrar":
            self.fields.pop("motivo")
        else:
            self.fields["motivo"].required = True
            self.fields["resultado"].choices = [(valor, texto) for valor, texto in self.fields["resultado"].choices if valor != reserva.resultado_uso]


class UsoMembresiaForm(forms.Form):
    modo = forms.ChoiceField(label="Período", choices=(("mes", "Mes completo"), ("rango", "Rango de fechas")), widget=forms.Select(attrs={"class": "form-control", "data-uso-modo": ""}))
    mes = forms.DateField(label="Mes", required=False, input_formats=["%Y-%m"], widget=forms.DateInput(format="%Y-%m", attrs={"type": "month", "class": "form-control"}))
    usuario = forms.ModelChoiceField(label="Titular", queryset=Usuario.objects.all().order_by("last_name", "first_name", "username"), widget=forms.Select(attrs={"class": "form-control"}))
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}))

    def __init__(self, *args, administrador=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not administrador:
            self.fields.pop("usuario")

    def clean(self):
        datos = super().clean()
        if datos.get("modo") == "mes":
            mes = datos.get("mes")
            if mes is None:
                self.add_error("mes", "Elegí un mes.")
            else:
                datos["desde"] = mes.replace(day=1)
                datos["hasta"] = mes.replace(day=monthrange(mes.year, mes.month)[1])
        elif datos.get("modo") == "rango":
            for campo in ("desde", "hasta"):
                if datos.get(campo) is None:
                    self.add_error(campo, "Indicá la fecha del período.")
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and (desde < FECHA_INICIO_OPERACIONES or hasta < desde or (hasta - desde).days > 365):
            raise forms.ValidationError("Elegí un período desde agosto de 2026 de hasta 366 días inclusive.")
        return datos
