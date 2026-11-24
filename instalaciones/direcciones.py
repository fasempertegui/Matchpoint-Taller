import json
import re
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError


PROVINCIA_CODIGO = "66"
PROVINCIA_NOMBRE = "Salta"

LOCALIDADES_SALTA = {
    "66028050": {
        "etiqueta": "Ciudad de Salta",
        "nombre_censal": "Salta",
    },
    "66077020": {
        "etiqueta": "Vaqueros",
        "nombre_censal": "Vaqueros",
    },
    "66028060": {
        "etiqueta": "San Lorenzo",
        "nombre_censal": "San Lorenzo",
    },
    "66035010": {
        "etiqueta": "Cerrillos",
        "nombre_censal": "San José de los Cerrillos",
    },
}

LOCALIDAD_CHOICES = tuple(
    (codigo, datos["etiqueta"]) for codigo, datos in LOCALIDADES_SALTA.items()
)

SAL_FORMULARIO_DIRECCION = "instalaciones.sede.direccion.formulario"
SAL_SELECCION_GEOREF = "instalaciones.sede.direccion.georef"

CORREO_ARGENTINO_CPA_URL = "https://www.correoargentino.com.ar/formularios/cpa"

_RE_ALTURA_NUMERICA = re.compile(
    r"^([1-9]\d{0,5})(?:[\s-]?([A-Za-z]|bis|ter|1/2))?$",
    re.IGNORECASE,
)
_RE_ALTURA_KM = re.compile(
    r"^(?:km\.?|kil[oó]metro)\s*([0-9]{1,4}(?:[.,][0-9]{1,2})?)$",
    re.IGNORECASE,
)
_RE_ALTURA_SN = re.compile(r"^s\s*/\s*n\.?$", re.IGNORECASE)
_RE_CPA = re.compile(r"^[A-HJ-NP-Z]\d{4}[A-Z]{3}$")
_RE_LETRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")


class ErrorServicioGeoref(Exception):
    """Error al consultar o interpretar la respuesta del servicio Georef."""


def etiqueta_localidad(localidad_codigo):
    datos = LOCALIDADES_SALTA.get(localidad_codigo)
    return datos["etiqueta"] if datos else ""


def validar_localidad_codigo(valor):
    codigo = (valor or "").strip()
    if codigo not in LOCALIDADES_SALTA:
        raise ValidationError("Seleccioná una localidad habilitada de Salta.")
    return codigo


def validar_calle(valor):
    calle = " ".join((valor or "").split())
    if len(calle) < 2:
        raise ValidationError("Ingresá el nombre de la calle o ruta.")
    if len(calle) > 150:
        raise ValidationError("El nombre de la calle no puede superar los 150 caracteres.")
    if not _RE_LETRA.search(calle):
        raise ValidationError("Ingresá un nombre de calle o ruta válido.")
    return calle


def validar_altura(valor):
    texto = " ".join((valor or "").split())
    if not texto:
        raise ValidationError("Ingresá la altura de la sede.")
    if len(texto) > 20:
        raise ValidationError("La altura no puede superar los 20 caracteres.")

    if _RE_ALTURA_SN.match(texto):
        return "s/n"

    coincidencia_km = _RE_ALTURA_KM.match(texto)
    if coincidencia_km:
        numero_km = coincidencia_km.group(1).replace(".", ",")
        return f"Km {numero_km}"

    coincidencia_num = _RE_ALTURA_NUMERICA.match(texto)
    if coincidencia_num:
        numero, sufijo = coincidencia_num.groups()
        if not sufijo:
            return numero
        sufijo_normalizado = (
            sufijo.lower() if sufijo.lower() in ("bis", "ter") else sufijo.upper()
        )
        return f"{numero} {sufijo_normalizado}"

    raise ValidationError(
        "Ingresá una altura válida (por ejemplo, 643, 643 B, 643 bis, Km 12 o s/n)."
    )


def validar_cpa(valor):
    cpa = re.sub(r"\s+", "", valor or "").upper()
    if not cpa:
        return ""
    if not _RE_CPA.match(cpa):
        raise ValidationError(
            "Ingresá el CPA completo de 8 caracteres (por ejemplo, A4400BKM) o dejalo vacío."
        )
    return cpa


def componer_direccion(calle, altura, localidad_codigo, cpa=""):
    localidad = etiqueta_localidad(localidad_codigo)
    calle_limpia = " ".join((calle or "").split())
    altura_limpia = " ".join((altura or "").split())
    if not (calle_limpia and altura_limpia and localidad):
        return ""
    base = f"{calle_limpia} {altura_limpia}, {localidad}, {PROVINCIA_NOMBRE}"
    cpa_limpio = re.sub(r"\s+", "", cpa or "").upper()
    if cpa_limpio:
        return f"{base} ({cpa_limpio})"
    return base


def crear_token_formulario_direccion(*, usuario_id, alcance, sede_id=None, nonce=None):
    return signing.dumps(
        {
            "usuario_id": usuario_id,
            "alcance": alcance,
            "sede_id": sede_id,
            "nonce": nonce or secrets.token_urlsafe(12),
        },
        salt=SAL_FORMULARIO_DIRECCION,
        compress=True,
    )


def validar_token_formulario_direccion(token, *, usuario_id, alcance, sede_id=None):
    max_age = getattr(settings, "GEOREF_FORMULARIO_MAX_AGE", 3600)
    try:
        datos = signing.loads(
            token or "",
            salt=SAL_FORMULARIO_DIRECCION,
            max_age=max_age,
        )
    except signing.SignatureExpired as error:
        raise ValidationError(
            "El formulario venció. Volvé a abrir el modal para buscar una dirección."
        ) from error
    except signing.BadSignature as error:
        raise ValidationError(
            "No se pudo validar el contexto del formulario. Volvé a abrir el modal."
        ) from error

    if (
        not isinstance(datos, dict)
        or datos.get("usuario_id") != usuario_id
        or datos.get("alcance") != alcance
        or datos.get("sede_id") != sede_id
        or not datos.get("nonce")
    ):
        raise ValidationError(
            "El contexto de búsqueda no corresponde a este formulario."
        )
    return datos


def firmar_seleccion_georef(
    *,
    usuario_id,
    alcance,
    sede_id,
    formulario_nonce,
    localidad_codigo,
    calle_georef_id,
    calle,
    altura_sugerida="",
):
    return signing.dumps(
        {
            "usuario_id": usuario_id,
            "alcance": alcance,
            "sede_id": sede_id,
            "formulario_nonce": formulario_nonce,
            "localidad_codigo": localidad_codigo,
            "calle_georef_id": calle_georef_id,
            "calle": calle,
            "altura_sugerida": altura_sugerida,
        },
        salt=SAL_SELECCION_GEOREF,
        compress=True,
    )


def validar_seleccion_georef(
    token,
    *,
    usuario_id,
    alcance,
    sede_id,
    formulario_nonce,
    localidad_codigo,
):
    max_age = getattr(settings, "GEOREF_SELECCION_MAX_AGE", 900)
    if not token:
        raise ValidationError(
            "Seleccioná una coincidencia de Georef o elegí la carga manual."
        )
    try:
        datos = signing.loads(
            token,
            salt=SAL_SELECCION_GEOREF,
            max_age=max_age,
        )
    except signing.SignatureExpired as error:
        raise ValidationError(
            "La selección de Georef venció. Buscá y elegí la calle nuevamente o ingresala manualmente."
        ) from error
    except signing.BadSignature as error:
        raise ValidationError(
            "La selección de Georef no es válida. Buscá y elegí la calle nuevamente."
        ) from error

    if (
        not isinstance(datos, dict)
        or datos.get("usuario_id") != usuario_id
        or datos.get("alcance") != alcance
        or datos.get("sede_id") != sede_id
        or datos.get("formulario_nonce") != formulario_nonce
    ):
        raise ValidationError(
            "La selección de Georef no corresponde a este formulario. Buscá la calle nuevamente."
        )

    if datos.get("localidad_codigo") != localidad_codigo:
        raise ValidationError(
            "La localidad cambió respecto de la calle seleccionada. Volvé a buscar en Georef."
        )

    calle_georef_id = (datos.get("calle_georef_id") or "").strip()
    calle = " ".join((datos.get("calle") or "").split())
    if (
        not calle_georef_id
        or len(calle_georef_id) > 20
        or not calle
        or len(calle) > 150
        or datos.get("localidad_codigo") not in LOCALIDADES_SALTA
    ):
        raise ValidationError(
            "Los datos firmados de Georef no son válidos. Buscá la calle nuevamente."
        )

    return {
        "localidad_codigo": datos["localidad_codigo"],
        "calle_georef_id": calle_georef_id,
        "calle": calle,
        "altura_sugerida": (datos.get("altura_sugerida") or "").strip(),
    }


def _formatear_altura_georef(altura_datos):
    if not isinstance(altura_datos, dict):
        return ""
    valor = altura_datos.get("valor")
    if valor is None or valor == "":
        return ""
    unidad = (altura_datos.get("unidad") or "").strip()
    if unidad:
        return f"{valor} {unidad}".strip()
    return str(valor).strip()


def buscar_direcciones_georef(consulta, localidad_codigo, *, limite=5):
    localidad_codigo = validar_localidad_codigo(localidad_codigo)
    texto = " ".join((consulta or "").split())
    if len(texto) < 2:
        raise ValidationError("Ingresá al menos 2 caracteres para buscar la calle.")
    if len(texto) > 150:
        raise ValidationError("La búsqueda no puede superar los 150 caracteres.")

    url_base = getattr(
        settings,
        "GEOREF_API_URL",
        "https://apis.datos.gob.ar/georef/api/direcciones",
    )
    timeout = getattr(settings, "GEOREF_TIMEOUT", 5)

    # Pedimos más resultados internos para deduplicar tramos repetidos de una misma calle.
    parametros = urlencode(
        {
            "direccion": texto,
            "provincia": PROVINCIA_CODIGO,
            "localidad_censal": localidad_codigo,
            "max": 15,
        }
    )
    peticion = Request(
        f"{url_base}?{parametros}",
        headers={
            "Accept": "application/json",
            "User-Agent": "AcademiaTM/1.0",
        },
    )

    try:
        with urlopen(peticion, timeout=timeout) as respuesta:
            if getattr(respuesta, "status", 200) != 200:
                raise ErrorServicioGeoref("Georef devolvió un estado no exitoso.")
            carga = json.loads(respuesta.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        raise ErrorServicioGeoref(
            "No se pudo consultar el servicio de direcciones Georef."
        ) from error

    direcciones = carga.get("direcciones")
    if not isinstance(direcciones, list):
        raise ErrorServicioGeoref("La respuesta de Georef no tiene el formato esperado.")

    resultados = []
    vistos = set()
    etiqueta_loc = etiqueta_localidad(localidad_codigo)

    for item in direcciones:
        if not isinstance(item, dict):
            continue
        provincia = item.get("provincia") or {}
        localidad = item.get("localidad_censal") or {}
        calle_datos = item.get("calle") or {}

        if str(provincia.get("id") or "") != PROVINCIA_CODIGO:
            continue
        if str(localidad.get("id") or "") != localidad_codigo:
            continue

        calle_georef_id = str(calle_datos.get("id") or "").strip()
        calle_nombre = " ".join(str(calle_datos.get("nombre") or "").split())
        if not calle_georef_id or not calle_nombre:
            continue
        if len(calle_georef_id) > 20 or len(calle_nombre) > 150:
            continue

        altura_sugerida = _formatear_altura_georef(item.get("altura"))
        clave = (calle_georef_id, altura_sugerida, localidad_codigo)
        if clave in vistos:
            continue
        vistos.add(clave)

        ubicacion = item.get("ubicacion")
        tiene_ubicacion = (
            isinstance(ubicacion, dict)
            and ubicacion.get("lat") is not None
            and ubicacion.get("lon") is not None
        )

        resultados.append(
            {
                "calle_georef_id": calle_georef_id,
                "calle": calle_nombre,
                "altura": altura_sugerida,
                "localidad_codigo": localidad_codigo,
                "localidad_etiqueta": etiqueta_loc,
                "provincia": PROVINCIA_NOMBRE,
                "tiene_ubicacion": tiene_ubicacion,
            }
        )
        if len(resultados) >= limite:
            break

    return resultados
