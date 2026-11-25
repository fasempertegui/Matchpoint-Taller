from html import escape
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COLOR_PRIMARIO = colors.HexColor("#4b176d")
COLOR_FONDO_PAGINA = colors.HexColor("#f4f1f8")
COLOR_ACENTO_SUAVE = colors.HexColor("#f4f8e2")
COLOR_BORDE = colors.HexColor("#d9dee5")


def generar_pdf(contexto, usuario):
    salida = BytesIO()
    ancho, alto = landscape(A4)
    ancho_util = ancho - 48
    estilo = ParagraphStyle("celda", fontName="Helvetica", fontSize=7.5, leading=10, spaceAfter=0)
    numero = ParagraphStyle("numero", parent=estilo, alignment=TA_RIGHT)
    encabezado = ParagraphStyle("encabezado", parent=estilo, fontName="Helvetica-Bold", textColor=colors.white)
    nota = ParagraphStyle("nota", parent=estilo, fontSize=8, leading=11, spaceAfter=7)
    pie = ParagraphStyle("pie", parent=estilo, fontSize=7, leading=9)

    def parrafo(texto, formato=estilo):
        return Paragraph(escape(str(texto)), formato)

    filtros = "Filtros: " + " | ".join(contexto["filtros_aplicados"])
    filtros_pdf = parrafo(filtros, pie)
    _, alto_filtros = filtros_pdf.wrap(ancho_util - 65, alto)
    generado = timezone.localtime(contexto["generado_en"]).strftime("%d/%m/%Y %H:%M:%S %Z")
    identidad = f"{usuario} (@{usuario.username})"
    usuario_pdf = parrafo(f"Emitido por {identidad} | {generado}", pie)
    _, alto_usuario = usuario_pdf.wrap(ancho_util - 65, alto)
    base_filtros = 12 + alto_usuario + 5
    alto_pie = base_filtros + alto_filtros + 8
    documento = SimpleDocTemplate(salida, pagesize=(ancho, alto), leftMargin=24, rightMargin=24,
                                 topMargin=76, bottomMargin=alto_pie + 12,
                                 title=contexto["reporte"]["titulo"], author=str(usuario))

    def pagina(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(COLOR_PRIMARIO)
        canvas.rect(0, alto - 8, ancho, 8, fill=1, stroke=0)
        logo = settings.BASE_DIR / "static" / "img" / "logo.png"
        if logo.exists():
            canvas.drawImage(str(logo), 24, alto - 53, width=32, height=32, mask="auto", preserveAspectRatio=True)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(66, alto - 31, "Academia TM")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(66, alto - 48, contexto["reporte"]["titulo"])
        canvas.setStrokeColor(COLOR_BORDE)
        canvas.line(24, alto_pie + 5, ancho - 24, alto_pie + 5)
        filtros_pdf.drawOn(canvas, 24, base_filtros)
        usuario_pdf.drawOn(canvas, 24, 12)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(ancho - 24, 15, f"Página {doc.page}")
        canvas.restoreState()

    columnas = contexto["columnas"]
    pesos = [columna[3] for columna in columnas]
    anchuras = [ancho_util * peso / sum(pesos) for peso in pesos]
    contenido = [parrafo(contexto["reporte"]["procesos"], nota)]
    contenido.extend(parrafo(texto, nota) for texto in contexto["reporte"]["notas"])
    contenido.append(Spacer(1, 6))
    datos = [[parrafo(columna[1], encabezado) for columna in columnas]]
    for fila in contexto["filas_pdf"]:
        datos.append([parrafo(valor, numero if columnas[i][2] in ("dinero", "entero", "porcentaje") else estilo)
                      for i, valor in enumerate(fila)])
    if not contexto["filas_pdf"]:
        datos.append([parrafo("No hay resultados para los filtros aplicados.")] + [""] * (len(columnas) - 1))
    datos.append([parrafo(valor, numero if i else estilo) for i, valor in enumerate(contexto["totales_tabla"])])
    resumen = f"{len(contexto['filas_pdf'])} filas. Totales de todo el resultado filtrado. "
    resumen += " | ".join(f"{etiqueta}: {valor}" for etiqueta, valor in contexto["indicadores"])
    datos.append([parrafo(resumen, nota)] + [""] * (len(columnas) - 1))
    tabla = Table(datos, colWidths=anchuras, repeatRows=1, hAlign="LEFT")
    instrucciones = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARIO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, COLOR_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, COLOR_FONDO_PAGINA]),
        ("BACKGROUND", (0, -2), (-1, -2), COLOR_ACENTO_SUAVE),
        ("SPAN", (0, -1), (-1, -1)),
        ("NOSPLIT", (0, -3), (-1, -1)),
    ]
    if not contexto["filas_pdf"]:
        instrucciones.append(("SPAN", (0, 1), (-1, 1)))
    tabla.setStyle(TableStyle(instrucciones))
    contenido.append(tabla)
    documento.build(contenido, onFirstPage=pagina, onLaterPages=pagina)
    return salida.getvalue()
