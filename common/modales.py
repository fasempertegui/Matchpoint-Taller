from django.http import JsonResponse
from django.template.loader import render_to_string

CABECERA_MODAL = "X-Modal-Formulario"


def es_peticion_modal(request):
    return request.headers.get(CABECERA_MODAL) == "1"


def respuesta_modal_html(request, plantilla, contexto, *, status=200, peligro=False, amplio=False, errores=False):
    html = render_to_string(plantilla, contexto, request=request)
    datos = {
        "ok": status < 400 and not errores,
        "html": html,
        "peligro": bool(peligro),
        "amplio": bool(amplio),
    }
    if errores:
        datos["errores"] = True
    return JsonResponse(datos, status=status)


def respuesta_modal_exito(redirect_url=""):
    return JsonResponse({"ok": True, "redirect": str(redirect_url) if redirect_url else ""})


def respuesta_modal_error(mensaje, *, status=400):
    return JsonResponse({"ok": False, "error": mensaje}, status=status)
