"""Plantilla Excel y exportaciones de perfiles de costeo."""

from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from services.perfiles_costeo import filas_exportables_perfiles

COLUMNAS = ["SKU", "TIPO", "UNIDAD", "OBSERVACION"]


def _libro(filas):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Productos"
    hoja.append(COLUMNAS)
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="176B89")
    for fila in filas:
        hoja.append([fila.get("sku", ""), fila.get("tipo", ""), fila.get("unidad", ""), fila.get("observacion", "")])
    for columna, ancho in zip("ABCD", (20, 18, 28, 50)):
        hoja.column_dimensions[columna].width = ancho
    hoja.freeze_panes = "A2"
    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida


def plantilla_excel_productos():
    return _libro([{"sku": "PP6040H", "tipo": "produccion", "unidad": "Fierro 100% Argento", "observacion": "Ejemplo: eliminar esta fila"}])


def exportar_excel_perfiles(perfiles):
    return _libro(filas_exportables_perfiles(perfiles))


def exportar_pdf_perfiles(perfiles, organizacion_nombre):
    salida = BytesIO()
    pdf = canvas.Canvas(salida, pagesize=landscape(A4))
    _ancho, alto = landscape(A4)
    y = alto - 42
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(36, y, "Productos y clasificacion de costos")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(36, y, organizacion_nombre)
    y -= 24
    for fila in filas_exportables_perfiles(perfiles):
        if y < 42:
            pdf.showPage()
            y = alto - 42
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(36, y, str(fila["sku"])[:24])
        pdf.setFont("Helvetica", 9)
        pdf.drawString(150, y, str(fila["producto"])[:60])
        pdf.drawString(470, y, str(fila["unidad"])[:32])
        pdf.drawString(650, y, str(fila["tipo"])[:18])
        y -= 16
    pdf.save()
    salida.seek(0)
    return salida
