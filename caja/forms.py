from decimal import Decimal
from uuid import uuid4

from django import forms

from .ingresos import ORIGENES
from .models import MovimientoFondo, SesionCaja


class AperturaCajaForm(forms.Form):
    efectivo_inicial = forms.DecimalField(label="Efectivo inicial", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    motivo_apertura = forms.CharField(min_length=5, label="Motivo si difiere del último contado", required=False, strip=True, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingresá al menos 5 caracteres"}))
    revision = forms.CharField(widget=forms.HiddenInput())
    contrasena = forms.CharField(label="Tu contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}), help_text="Confirmá tu contraseña para abrir la caja.")


class CierreCajaForm(forms.Form):
    efectivo_contado = forms.DecimalField(label="Efectivo contado", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    motivo_diferencia = forms.CharField(min_length=5, label="Motivo si hay diferencia", required=False, strip=True, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingresá al menos 5 caracteres"}))
    contrasena = forms.CharField(label="Tu contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}), help_text="Confirmá tu contraseña para cerrar la caja.")


class SeleccionOrigenMovimientoForm(forms.Form):
    origen = forms.ModelChoiceField(label="Reserva o contratación", queryset=None, empty_label="Elegí un registro", widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, tipo, devolucion=False, **kwargs):
        super().__init__(*args, **kwargs)
        modelo = ORIGENES[tipo][0]
        if tipo == "reserva":
            consulta = modelo.objects.all().select_related("organizador", "evento__turno__cancha__sede").prefetch_related("invitados")
            self.fields["origen"].label_from_instance = lambda r: f"{r.numero}, {r.organizador}, {r.evento.turno}"
        else:
            consulta = modelo.objects.all().select_related("usuario", "plan" if tipo == "plan" else "membresia")
        if not devolucion:
            consulta = consulta.exclude(**{"evento__estado" if tipo == "reserva" else "estado": "anulado"})
        self.fields["origen"].queryset = consulta.prefetch_related("ajustes_importe")


class IngresoForm(forms.Form):
    concepto = forms.CharField(label="Concepto", strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}), help_text="Describí el cobro y cualquier parcial o acuerdo que corresponda")
    monto = forms.DecimalField(label="Monto recibido", min_value=Decimal("0.01"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    medio_pago = forms.ChoiceField(label="Medio de pago", widget=forms.Select(attrs={"class": "form-control", "data-ingreso-medio": ""}))
    referencia = forms.CharField(label="Referencia del pago", max_length=150, required=False, strip=True, widget=forms.TextInput(attrs={"class": "form-control"}))
    verificado = forms.BooleanField(label="Verifiqué la recepción del pago o la aprobación de la operación con tarjeta", required=False)
    operacion_id = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, sin_vinculo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operacion_id"].initial = uuid4()
        self.fields["medio_pago"].choices = [("", "Elegí un medio"), *MovimientoFondo.Medio.choices]
        if sin_vinculo:
            self.fields["sin_vinculo_confirmado"] = forms.BooleanField(label="Este movimiento no corresponde a una reserva ni a una contratación.")

    def clean(self):
        datos = super().clean()
        if datos.get("medio_pago") in ("transferencia", "tarjeta", "qr"):
            if not datos.get("referencia"):
                self.add_error("referencia", "Indicá una referencia del pago.")
            if not datos.get("verificado"):
                self.add_error("verificado", "Verificá manualmente el pago antes de registrarlo.")
        return datos


class MovimientoCajaForm(IngresoForm):
    categoria_egreso = forms.ChoiceField(label="Categoría", required=False, widget=forms.Select(attrs={"class": "form-control", "data-categoria-egreso": ""}))
    destinatario = forms.CharField(label="Destinatario (opcional)", max_length=150, required=False, strip=True, widget=forms.TextInput(attrs={"class": "form-control"}))

    def __init__(self, *args, clase, **kwargs):
        super().__init__(*args, **kwargs)
        self.clase = clase
        self.fields["concepto"].widget = forms.TextInput(attrs={"class": "form-control", "autofocus": clase in ("aporte", "retiro")})
        if clase == "egreso":
            self.fields["concepto"].help_text = "Describí el pago realizado."
        elif clase == "aporte":
            self.fields["concepto"].help_text = "Explicá el aporte de efectivo."
        else:
            self.fields["concepto"].help_text = "Explicá el retiro de efectivo."
        self.fields["monto"].label = "Monto"
        self.fields["verificado"].label = "Verifiqué el pago realizado o la aprobación de la operación con tarjeta"
        self.fields["categoria_egreso"].choices = [("", "Elegí una categoría"), *MovimientoFondo.CategoriaEgreso.choices]
        if clase == "egreso":
            self.fields["categoria_egreso"].required = True
        else:
            for nombre in ("categoria_egreso", "destinatario", "medio_pago", "referencia", "verificado"):
                self.fields.pop(nombre)
        self.order_fields(["categoria_egreso", "concepto", "monto", "medio_pago", "referencia", "verificado", "destinatario", "operacion_id"])

    def clean(self):
        datos = super().clean()
        if self.clase in ("aporte", "retiro"):
            datos["medio_pago"] = "efectivo"
        if datos.get("categoria_egreso") == "devoluciones":
            self.add_error("categoria_egreso", "Las devoluciones deben vincularse a una reserva o contratación. Usá «Vincular operación» o elegí la categoría Otros.")
        return datos


class DevolucionForm(MovimientoCajaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, clase="egreso", **kwargs)
        self.fields.pop("categoria_egreso")
        self.fields["concepto"].help_text = "Explicá el motivo de la devolución."
        self.fields["monto"].label = "Monto a devolver"


class ExcedenteForm(IngresoForm):
    motivo_excedente = forms.CharField(
        label="Motivo del cobro con excedente",
        min_length=5,
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingresá al menos 5 caracteres"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concepto"].widget = forms.TextInput(attrs={"class": "form-control"})


class AjusteImporteForm(forms.Form):
    importe_nuevo = forms.DecimalField(label="Nuevo importe acordado", min_value=Decimal("0.00"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    motivo = forms.CharField(label="Motivo", min_length=5, strip=True, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ingresá al menos 5 caracteres"}))
    operacion_id = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operacion_id"].initial = uuid4()


class AnulacionMovimientoForm(forms.Form):
    motivo = forms.CharField(
        min_length=5,
        label="Motivo de anulación",
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True, "placeholder": "Ingresá al menos 5 caracteres"}),
    )
    revision = forms.CharField(widget=forms.HiddenInput())


class RevisionDiferenciaForm(forms.Form):
    conclusion = forms.CharField(
        min_length=5,
        label="Conclusión de la revisión",
        strip=True,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True, "placeholder": "Ingresá al menos 5 caracteres"}),
    )


class HistorialSesionesForm(forms.Form):
    desde = forms.DateField(label="Apertura desde", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    hasta = forms.DateField(label="Apertura hasta", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    estado = forms.ChoiceField(label="Estado", required=False, widget=forms.Select(attrs={"class": "form-control"}))
    revision = forms.ChoiceField(label="Revisión de diferencias", required=False, widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [("", "Todos"), *SesionCaja.Estado.choices]
        self.fields["revision"].choices = [
            ("", "Todas"),
            ("pendiente", "Pendiente de revisión"),
            ("revisada", "Revisada"),
            ("sin_diferencias", "Sin diferencias"),
        ]

    def clean(self):
        datos = super().clean()
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise forms.ValidationError("La fecha hasta debe ser igual o posterior a desde.")
        return datos


class HistorialMovimientosForm(HistorialSesionesForm):
    clase = forms.ChoiceField(label="Clase", required=False, widget=forms.Select(attrs={"class": "form-control"}))
    medio_pago = forms.ChoiceField(label="Medio", required=False, widget=forms.Select(attrs={"class": "form-control"}))
    categoria = forms.ChoiceField(label="Categoría", required=False, widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("revision", None)
        self.fields["desde"].label = "Registro desde"
        self.fields["hasta"].label = "Registro hasta"
        self.fields["estado"].choices = [("", "Todos"), *MovimientoFondo.Estado.choices]
        self.fields["clase"].choices = [("", "Todas"), *MovimientoFondo.Clase.choices]
        self.fields["medio_pago"].choices = [("", "Todos"), *MovimientoFondo.Medio.choices]
        clase = self.data.get("clase", "")
        categorias = {
            "ingreso": MovimientoFondo.CategoriaIngreso.choices,
            "egreso": MovimientoFondo.CategoriaEgreso.choices,
        }.get(clase, [])
        self.fields["categoria"].disabled = not categorias
        self.fields["categoria"].choices = [("", "Todas" if categorias else "Elegí ingreso o egreso")] + [
            (f"{clase}:{valor}", texto) for valor, texto in categorias
        ]
        self.order_fields(["desde", "hasta", "clase", "categoria", "estado", "medio_pago"])
        if self.is_bound and self.data.get("categoria") and not self.data["categoria"].startswith(f"{clase}:"):
            self.data = self.data.copy()
            self.data["categoria"] = ""


class MovimientosSesionForm(HistorialMovimientosForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("desde", "hasta", "estado"):
            self.fields.pop(campo)
        self.order_fields(["medio_pago", "clase", "categoria"])
