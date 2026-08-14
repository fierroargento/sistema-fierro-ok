"""Plantillas XLSX de conteo sin dependencias de planilla en ejecución."""

from io import BytesIO
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile


ENCABEZADOS = ("SKU", "UBICACION", "ESPERADO", "CONTADO", "OBSERVACION")
NS_HOJA = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def obtener_conteo_tenant(conteo_id, organizacion_id, *, modelos):
    """Resuelve el conteo dentro del tenant fuera de la capa HTTP."""
    Conteo = modelos["ConteoInventario"]
    return Conteo.query.filter_by(
        id=int(conteo_id), organizacion_id=int(organizacion_id)
    ).first()


def _columna(numero):
    letras = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def crear_xlsx_conteo(filas):
    """Construye un XLSX estándar usando únicamente la biblioteca base."""
    filas_xml = []
    for numero_fila, fila in enumerate(filas, 1):
        celdas = []
        for numero_columna, valor in enumerate(fila, 1):
            referencia = f"{_columna(numero_columna)}{numero_fila}"
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                celdas.append(f'<c r="{referencia}"><v>{valor}</v></c>')
            else:
                texto = escape("" if valor is None else str(valor))
                celdas.append(
                    f'<c r="{referencia}" t="inlineStr"><is><t>{texto}</t></is></c>'
                )
        filas_xml.append(f'<row r="{numero_fila}">{"".join(celdas)}</row>')
    hoja = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS_HOJA}"><sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews><sheetData>'
        + "".join(filas_xml)
        + '</sheetData><autoFilter ref="A1:E1"/></worksheet>'
    )
    contenido = BytesIO()
    with ZipFile(contenido, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        archivo.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        archivo.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Conteo físico" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archivo.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        archivo.writestr("xl/worksheets/sheet1.xml", hoja)
    contenido.seek(0)
    return contenido


def crear_plantilla_conteo(conteo):
    filas = [ENCABEZADOS]
    for item in conteo.items:
        existencia = item.existencia
        sku = (
            existencia.item_inventario.sku
            if existencia.item_inventario is not None
            else existencia.producto.sku
        )
        filas.append((
            sku, conteo.sucursal.nombre, int(item.cantidad_esperada),
            item.cantidad_contada, item.observacion or "",
        ))
    return crear_xlsx_conteo(filas)


def _texto_celda(celda, compartidos):
    tipo = celda.attrib.get("t")
    if tipo == "inlineStr":
        return "".join(celda.itertext())
    valor = celda.findtext(f"{{{NS_HOJA}}}v")
    if tipo == "s" and valor not in (None, ""):
        return compartidos[int(valor)]
    return valor


def _leer_filas_xlsx(archivo):
    try:
        datos = archivo.read()
        with ZipFile(BytesIO(datos)) as libro:
            compartidos = []
            if "xl/sharedStrings.xml" in libro.namelist():
                raiz_textos = ET.fromstring(libro.read("xl/sharedStrings.xml"))
                compartidos = ["".join(nodo.itertext()) for nodo in raiz_textos]
            raiz = ET.fromstring(libro.read("xl/worksheets/sheet1.xml"))
    except (BadZipFile, KeyError, ET.ParseError) as error:
        raise ValueError("El archivo XLSX no es válido o está dañado.") from error
    filas = []
    for fila in raiz.findall(f".//{{{NS_HOJA}}}row"):
        valores = [None] * len(ENCABEZADOS)
        for celda in fila.findall(f"{{{NS_HOJA}}}c"):
            referencia = celda.attrib.get("r", "")
            letras = "".join(c for c in referencia if c.isalpha())
            columna = 0
            for letra in letras:
                columna = columna * 26 + ord(letra.upper()) - 64
            if 1 <= columna <= len(valores):
                valores[columna - 1] = _texto_celda(celda, compartidos)
        filas.append(tuple(valores))
    return filas


def importar_conteo_excel(conteo, archivo, *, db_session):
    if conteo.estado == "conciliado":
        raise ValueError("El inventario ya fue conciliado y no admite cambios.")
    nombre = str(getattr(archivo, "filename", "") or "").lower()
    if not nombre.endswith(".xlsx"):
        raise ValueError("El archivo debe estar en formato XLSX.")
    filas = _leer_filas_xlsx(archivo)
    encabezados = tuple(str(v or "").strip().upper() for v in (filas[0] if filas else ()))
    if encabezados != ENCABEZADOS:
        raise ValueError("La plantilla no corresponde a un conteo de inventario.")
    items_por_sku = {}
    for item in conteo.items:
        existencia = item.existencia
        sku = existencia.item_inventario.sku if existencia.item_inventario is not None else existencia.producto.sku
        items_por_sku[str(sku).strip().upper()] = item
    recibidos = set()
    cambios = []
    for fila in filas[1:]:
        sku = str(fila[0] or "").strip().upper()
        if not sku and all(valor in (None, "") for valor in fila):
            continue
        if sku not in items_por_sku:
            raise ValueError(f"El SKU {sku or '(vacío)'} no pertenece al inventario.")
        if sku in recibidos:
            raise ValueError(f"El SKU {sku} está repetido en la plantilla.")
        try:
            numero = float(fila[3])
            cantidad = int(numero)
            if numero != cantidad:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise ValueError(f"Completá una cantidad entera para {sku}.") from error
        if cantidad < 0:
            raise ValueError(f"La cantidad de {sku} no puede ser negativa.")
        cambios.append((items_por_sku[sku], cantidad, str(fila[4] or "").strip()[:300] or None))
        recibidos.add(sku)
    faltantes = sorted(set(items_por_sku) - recibidos)
    if faltantes:
        raise ValueError("Faltan SKU por contar: " + ", ".join(faltantes[:10]))
    for item, cantidad, observacion in cambios:
        item.cantidad_contada = cantidad
        item.diferencia = cantidad - int(item.cantidad_esperada)
        item.observacion = observacion
    conteo.estado = "contado"
    db_session.commit()
    return len(cambios)
