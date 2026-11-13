from decimal import Decimal
from uuid import uuid4

from django import forms

from .ingresos import ORIGENES
from .models import MovimientoFondo, SesionCaja


class AperturaCajaForm(forms.Form):
    efectivo_inicial = forms.DecimalField(label="Efectivo inicial", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    motivo_apertura = forms.CharField(min_length=5, label="Motivo si difiere del último contado", required=False, strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    revision = forms.CharField(widget=forms.HiddenInput())
    contrasena = forms.CharField(label="Tu contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}), help_text="Confirmá tu contraseña para abrir la caja.")


class CierreCajaForm(forms.Form):
    efectivo_contado = forms.DecimalField(label="Efectivo contado", min_value=Decimal("0"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    motivo_diferencia = forms.CharField(min_length=5, label="Motivo si hay diferencia", required=False, strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    contrasena = forms.CharField(label="Tu contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}), help_text="Confirmá tu contraseña para cerrar la caja.")


class SeleccionOrigenMovimientoForm(forms.Form):
    origen = forms.ModelChoiceField(label="Reserva o contratación", queryset=None, empty_label="Elegí un registro", widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, tipo, devolucion=False, **kwargs):
        super().__init__(*args, **kwargs)
        modelo = ORIGENES[tipo][0]
        if tipo == "reserva":
            consulta = modelo.objects.all().select_related("organizador", "evento__turno__cancha__sede").prefetch_related("invitados")
            self.fields["origen"].label_from_instance = lambda r: f"{r.numero} · {r.organizador} · {r.evento.turno}"
        else:
            consulta = modelo.objects.all().select_related("usuario", "plan" if tipo == "plan" else "membresia")
        if not devolucion:
            consulta = consulta.exclude(**{"evento__estado" if tipo == "reserva" else "estado": "anulado"})
        self.fields["origen"].queryset = consulta


class IngresoForm(forms.Form):
    concepto = forms.CharField(label="Concepto", strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}), help_text="Describí el cobro y cualquier parcial o acuerdo que corresponda")
    monto = forms.DecimalField(label="Monto recibido", min_value=Decimal("0.01"), max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Pesos argentinos"}))
    medio_pago = forms.ChoiceField(label="Medio de pago", widget=forms.Select(attrs={"class": "form-control", "data-ingreso-medio": ""}))
    referencia = forms.CharField(label="Referencia del pago", max_length=150, required=False, strip=True, widget=forms.TextInput(attrs={"class": "form-control"}))
    verificado = forms.BooleanField(label="Verifiqué la recepción del pago o la aprobación de la operación con tarjeta", required=False)
    operacion_id = forms.UUIDField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operacion_id"].initial = uuid4()
        self.fields["medio_pago"].choices = [("", "Elegí un medio"), *MovimientoFondo.Medio.choices]

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
        self.fields["concepto"].help_text = "Describí el pago realizado." if clase == "egreso" else "Explicá el aporte o retiro de efectivo."
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
        return datos


class DevolucionForm(MovimientoCajaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, clase="egreso", **kwargs)
        self.fields.pop("categoria_egreso")
        self.fields["concepto"].help_text = "Explicá el motivo de la devolución."
        self.fields["monto"].label = "Monto a devolver"


class AnulacionMovimientoForm(forms.Form):
    motivo = forms.CharField(min_length=5, label="Motivo de anulación", strip=True, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    revision = forms.CharField(widget=forms.HiddenInput())


class HistorialSesionesForm(forms.Form):
    desde = forms.DateField(label="Apertura desde", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    hasta = forms.DateField(label="Apertura hasta", required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    estado = forms.ChoiceField(label="Estado", required=False, widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [("", "Todos"), *SesionCaja.Estado.choices]

    def clean(self):
        datos = super().clean()
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise forms.ValidationError("La fecha hasta debe ser igual o posterior a desde.")
        return datos


class HistorialMovimientosForm(HistorialSesionesForm):
    sesion = forms.ModelChoiceField(label="Sesión", queryset=None, required=False, widget=forms.Select(attrs={"class": "form-control"}))
    clase = forms.ChoiceField(label="Clase", required=False, widget=forms.Select(attrs={"class": "form-control"}))
    medio_pago = forms.ChoiceField(label="Medio", required=False, widget=forms.Select(attrs={"class": "form-control"}))
    categoria = forms.ChoiceField(label="Categoría", required=False, widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["desde"].label = "Registro desde"
        self.fields["hasta"].label = "Registro hasta"
        self.fields["estado"].choices = [("", "Todos"), *MovimientoFondo.Estado.choices]
        self.fields["sesion"].queryset = SesionCaja.objects.all()
        self.fields["clase"].choices = [("", "Todas"), *MovimientoFondo.Clase.choices]
        self.fields["medio_pago"].choices = [("", "Todos"), *MovimientoFondo.Medio.choices]
        self.fields["categoria"].choices = [("", "Todas")] + [
            (f"{clase}:{valor}", f"{clase.title()} · {texto}")
            for clase, categorias in [("ingreso", MovimientoFondo.CategoriaIngreso.choices), ("egreso", MovimientoFondo.CategoriaEgreso.choices)]
            for valor, texto in categorias
        ]
