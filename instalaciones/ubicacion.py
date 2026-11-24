import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from shapely import prepare
from shapely.geometry import Point, shape


RUTA_GEOJSON_LOCALIDADES = (
    Path(__file__).resolve().parent / "datos" / "localidades_salta_indec.geojson"
)

PRECISION_COORDENADA = Decimal("0.000001")
LATITUD_MIN = Decimal("-90.000000")
LATITUD_MAX = Decimal("90.000000")
LONGITUD_MIN = Decimal("-180.000000")
LONGITUD_MAX = Decimal("180.000000")

ATRIBUCION_OSM_PREDETERMINADA = (
    '© <a href="https://www.openstreetmap.org/copyright" target="_blank" '
    'rel="noopener noreferrer">OpenStreetMap</a>'
)


@lru_cache(maxsize=1)
def cargar_geometrias_localidades():
    with RUTA_GEOJSON_LOCALIDADES.open("r", encoding="utf-8") as archivo:
        coleccion = json.load(archivo)

    geometrias = {}
    for feature in coleccion.get("features", []):
        propiedades = feature.get("properties") or {}
        codigo = str(propiedades.get("codigo") or "").strip()
        if not codigo:
            continue
        geometria = shape(feature["geometry"])
        prepare(geometria)
        punto_centro = geometria.representative_point()
        geometrias[codigo] = {
            "geometria": geometria,
            "etiqueta": propiedades.get("etiqueta", ""),
            "centro": {
                "lat": float(Decimal(str(punto_centro.y)).quantize(PRECISION_COORDENADA, rounding=ROUND_HALF_UP)),
                "lon": float(Decimal(str(punto_centro.x)).quantize(PRECISION_COORDENADA, rounding=ROUND_HALF_UP)),
            },
        }
    return geometrias


def centros_localidades():
    return {
        codigo: datos["centro"]
        for codigo, datos in cargar_geometrias_localidades().items()
    }


def cuantizar_coordenada(valor):
    if isinstance(valor, Decimal):
        numero = valor
    else:
        texto = str(valor).strip().replace(",", ".")
        numero = Decimal(texto)
    if not numero.is_finite():
        raise InvalidOperation("Coordenada no finita")
    return numero.quantize(PRECISION_COORDENADA, rounding=ROUND_HALF_UP)


def validar_par_coordenadas(latitud_raw, longitud_raw):
    lat_texto = ("" if latitud_raw is None else str(latitud_raw)).strip()
    lon_texto = ("" if longitud_raw is None else str(longitud_raw)).strip()

    if not lat_texto and not lon_texto:
        return None, None

    errores = {}
    latitud = None
    longitud = None

    if not lat_texto:
        errores["latitud_entrada"] = "Ingresá la latitud junto con la longitud."
    else:
        try:
            latitud = cuantizar_coordenada(lat_texto)
        except InvalidOperation:
            errores["latitud_entrada"] = "Ingresá una latitud numérica válida (por ejemplo, -24.781872)."
        else:
            if latitud < LATITUD_MIN or latitud > LATITUD_MAX:
                errores["latitud_entrada"] = "La latitud debe estar entre -90 y 90."

    if not lon_texto:
        errores["longitud_entrada"] = "Ingresá la longitud junto con la latitud."
    else:
        try:
            longitud = cuantizar_coordenada(lon_texto)
        except InvalidOperation:
            errores["longitud_entrada"] = "Ingresá una longitud numérica válida (por ejemplo, -65.411627)."
        else:
            if longitud < LONGITUD_MIN or longitud > LONGITUD_MAX:
                errores["longitud_entrada"] = "La longitud debe estar entre -180 y 180."

    if errores:
        raise ValidationError(errores)

    return latitud, longitud


def punto_en_localidad(localidad_codigo, latitud, longitud):
    if not localidad_codigo or latitud is None or longitud is None:
        return False
    datos = cargar_geometrias_localidades().get(localidad_codigo)
    if datos is None:
        return False
    try:
        lat_dec = cuantizar_coordenada(latitud)
        lon_dec = cuantizar_coordenada(longitud)
    except InvalidOperation:
        return False
    if (
        lat_dec < LATITUD_MIN
        or lat_dec > LATITUD_MAX
        or lon_dec < LONGITUD_MIN
        or lon_dec > LONGITUD_MAX
    ):
        return False
    # Shapely utiliza orden (longitud, latitud) en WGS 84.
    punto = Point(float(lon_dec), float(lat_dec))
    return bool(datos["geometria"].covers(punto))


def enlace_como_llegar(latitud, longitud):
    if latitud is None or longitud is None:
        return ""
    lat_str = f"{cuantizar_coordenada(latitud):.6f}"
    lon_str = f"{cuantizar_coordenada(longitud):.6f}"
    return f"https://www.google.com/maps/dir/?api=1&destination={lat_str},{lon_str}"


def configuracion_mapa():
    return {
        "teselas_url": getattr(
            settings,
            "MAPA_TESELAS_URL",
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        ),
        "atribucion": getattr(
            settings,
            "MAPA_ATRIBUCION",
            ATRIBUCION_OSM_PREDETERMINADA,
        ),
        "zoom_max": int(getattr(settings, "MAPA_ZOOM_MAX", 19)),
    }
