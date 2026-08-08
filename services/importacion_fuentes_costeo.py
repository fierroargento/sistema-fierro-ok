"""Contratos separados para carga masiva de fuentes y fichas productivas."""

from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from services.importacion_productos_costeo import normalizar

try:
    from openpyxl.styles import Font, PatternFill
except ImportError:  # El runtime minimo de pruebas no expone estilos.
    Font = PatternFill = None


DEFINICIONES = {
    "insumos": {
        "titulo": "Insumos y precios",
        "campos": {
            "codigo": ("Código", True), "nombre": ("Nombre", True),
            "tipo": ("Tipo", True), "unidad_medida": ("Unidad de medida", True),
            "precio_unitario": ("Precio unitario", True), "proveedor": ("Proveedor", False),
        },
        "ejemplo": ["hierro-6mm", "Hierro redondo 6 mm", "materia_prima", "kg", "1500", "Proveedor"],
    },
    "empleados": {
        "titulo": "Empleados y costos laborales",
        "campos": {
            "codigo": ("Código o legajo", True), "nombre": ("Nombre", True),
            "sector": ("Sector", True), "puesto": ("Puesto", False),
            "sueldo_base": ("Sueldo base", True), "cargas_sociales": ("Cargas sociales", False),
            "adicionales": ("Adicionales", False), "otros_costos": ("Otros costos", False),
            "horas_mensuales": ("Horas mensuales", True), "horas_productivas": ("Horas productivas", True),
        },
        "ejemplo": ["EMP-1", "Operario", "Herrería", "Soldador", "1000000", "300000", "0", "0", "176", "160"],
    },
    "costos-fijos": {
        "titulo": "Costos fijos",
        "campos": {
            "codigo": ("Código", True), "nombre": ("Nombre", True),
            "categoria": ("Categoría", True), "integra_produccion": ("Integra producción", True),
            "criterio": ("Criterio de distribución", True), "importe_mensual": ("Importe mensual", True),
            "comprobante": ("Comprobante", False),
        },
        "ejemplo": ["alquiler", "Alquiler del galpón", "Infraestructura", "si", "unidades_producidas", "500000", "Factura"],
    },
    "fichas": {
        "titulo": "Componentes de fichas técnicas",
        "campos": {
            "sku": ("SKU producto", True), "tipo_linea": ("Tipo de línea", True),
            "codigo_recurso": ("Código del recurso", True), "cantidad": ("Cantidad", False),
            "merma": ("Merma %", False), "operacion": ("Operación", False),
            "minutos": ("Minutos", False), "porcentaje": ("Asignación %", False),
            "unidades_mensuales": ("Unidades mensuales", False),
        },
        "ejemplo": ["PP6040H", "insumo", "hierro-6mm", "2.5", "5", "", "", "", ""],
    },
}


def definicion(tipo):
    if tipo not in DEFINICIONES:
        raise ValueError("El tipo de importación no es válido.")
    base = DEFINICIONES[tipo]
    return {
        **base,
        "campos_ui": {
            clave: {"nombre": datos[0], "obligatorio": datos[1]}
            for clave, datos in base["campos"].items()
        },
    }


def sugerir_mapeo_fuente(tipo, encabezados):
    campos = definicion(tipo)["campos"]
    resultado, usados = {}, set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(str(encabezado or "").replace("_", " ").replace("-", " "))
        destino = ""
        for clave, (nombre, _obligatorio) in campos.items():
            opciones = {normalizar(nombre), normalizar(clave.replace("_", " "))}
            if clave not in usados and limpio in opciones:
                destino, usados = clave, usados | {clave}
                break
        resultado[str(indice)] = destino
    return resultado


def _extraer(fila, mapeo):
    return {
        campo: (fila["valores"][int(indice)] if int(indice) < len(fila["valores"]) else "")
        for indice, campo in mapeo.items() if campo
    }


def _numero(valor, nombre, obligatorio=True):
    if not str(valor or "").strip() and not obligatorio:
        return "0"
    try:
        numero = Decimal(str(valor).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{nombre} no es válido") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"{nombre} no es válido")
    return str(numero)


def previsualizar_fuentes(tipo, filas, mapeo, *, organizacion_id, unidad_negocio_id, modelos):
    config = definicion(tipo)
    destinos = [campo for campo in mapeo.values() if campo]
    faltantes = [nombre for clave, (nombre, obligatorio) in config["campos"].items() if obligatorio and clave not in destinos]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")
    if len(destinos) != len(set(destinos)):
        raise ValueError("Un campo del sistema no puede recibir dos columnas.")
    resultado = []
    for fila in filas:
        datos, errores, existente, ids = _extraer(fila, mapeo), [], None, {}
        try:
            if tipo == "insumos":
                existente = modelos["InsumoProductivo"].query.filter_by(organizacion_id=organizacion_id, codigo=str(datos.get("codigo") or "").strip().lower()).first()
                if existente: ids = {"insumo_id": existente.id}
                _numero(datos.get("precio_unitario"), "Precio unitario")
            elif tipo == "empleados":
                existente = modelos["EmpleadoProductivo"].query.filter_by(organizacion_id=organizacion_id, codigo=str(datos.get("codigo") or "").strip().lower()).first()
                if existente: ids = {"empleado_id": existente.id}
                for campo in ("sueldo_base", "cargas_sociales", "adicionales", "otros_costos", "horas_mensuales", "horas_productivas"):
                    datos[campo] = _numero(datos.get(campo), campo, campo in {"sueldo_base", "horas_mensuales", "horas_productivas"})
            elif tipo == "costos-fijos":
                existente = modelos["CostoFijoProductivo"].query.filter_by(organizacion_id=organizacion_id, codigo=str(datos.get("codigo") or "").strip().lower()).first()
                if existente: ids = {"costo_fijo_id": existente.id}
                _numero(datos.get("importe_mensual"), "Importe mensual")
            else:
                sku = str(datos.get("sku") or "").strip().upper()
                perfil = modelos["PerfilCosteoProducto"].query.join(modelos["Producto"]).filter(
                    modelos["PerfilCosteoProducto"].organizacion_id == organizacion_id,
                    modelos["PerfilCosteoProducto"].unidad_negocio_id == unidad_negocio_id,
                    modelos["PerfilCosteoProducto"].tipo == "produccion",
                    modelos["Producto"].sku.ilike(sku),
                ).first()
                if perfil is None: raise ValueError("No se encontró el producto de producción")
                linea = normalizar(datos.get("tipo_linea"))
                codigo = str(datos.get("codigo_recurso") or "").strip().lower()
                mapa = {"insumo": ("InsumoProductivo", "insumo_id"), "operacion": ("EmpleadoProductivo", "empleado_id"), "costo fijo": ("CostoFijoProductivo", "costo_fijo_id"), "fijo": ("CostoFijoProductivo", "costo_fijo_id")}
                if linea not in mapa: raise ValueError("Tipo de línea inválido")
                nombre_modelo, campo_id = mapa[linea]
                recurso = modelos[nombre_modelo].query.filter_by(organizacion_id=organizacion_id, codigo=codigo).first()
                if recurso is None or recurso.unidad_negocio_id not in {None, unidad_negocio_id}: raise ValueError("No se encontró el recurso en la unidad activa")
                ids = {"perfil_costeo_id": perfil.id, campo_id: recurso.id}
                existente = True
        except ValueError as error:
            errores.append(str(error))
        resultado.append({"numero": fila["numero"], "datos": datos, "ids": ids, "accion": "rechazado" if errores else "actualizar" if existente else "crear", "errores": errores})
    return resultado


def plantilla_excel_fuente(tipo):
    config = definicion(tipo); libro = Workbook(); hoja = libro.active
    hoja.title = config["titulo"][:31]
    hoja.append([nombre.upper() for nombre, _ in config["campos"].values()]); hoja.append(config["ejemplo"])
    if Font is not None and PatternFill is not None:
        for celda in hoja[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="176B89")
    hoja.freeze_panes = "A2"
    for columna in hoja.columns:
        hoja.column_dimensions[columna[0].column_letter].width = max(16, min(32, len(str(columna[0].value)) + 4))
    salida = BytesIO(); libro.save(salida); salida.seek(0); return salida


def aplicar_fuentes(tipo, vista, *, organizacion, unidad_activa, modelos, db_session, usuario):
    from services.fuentes_costo_admin import procesar_accion_fuente_costo
    conteos = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "rechazados": 0}
    for fila in vista:
        if fila["accion"] == "rechazado":
            conteos["rechazados"] += 1; continue
        datos = dict(fila["datos"]); datos.update(fila.get("ids") or {})
        datos["unidad_negocio_id"] = str(unidad_activa.id)
        if tipo == "insumos":
            accion = "crear_insumo" if fila["accion"] == "crear" else "actualizar_precio_insumo"
            datos.update({"insumo_id": datos.get("insumo_id"), "precio_unitario": datos.get("precio_unitario"), "proveedor_referencia": datos.get("proveedor")})
        elif tipo == "empleados":
            accion = "crear_empleado" if fila["accion"] == "crear" else "actualizar_costo_empleado"
            datos["empleado_id"] = datos.get("empleado_id")
        elif tipo == "costos-fijos":
            accion = "crear_costo_fijo" if fila["accion"] == "crear" else "actualizar_importe_costo_fijo"
            datos.update({"costo_fijo_id": datos.get("costo_fijo_id"), "integra_costo_produccion": "1" if normalizar(datos.get("integra_produccion")) in {"si", "sí", "1", "true"} else "0", "criterio_distribucion": datos.get("criterio"), "comprobante_referencia": datos.get("comprobante")})
        else:
            linea = normalizar(datos.get("tipo_linea"))
            accion = "ficha_insumo" if linea == "insumo" else "ficha_operacion" if linea == "operacion" else "ficha_costo_fijo"
            datos.update({"merma": datos.get("merma", 0), "nombre_operacion": datos.get("operacion"), "porcentaje": datos.get("porcentaje")})
        procesar_accion_fuente_costo(
            accion, datos, organizacion=organizacion, unidad_activa=unidad_activa,
            modelos=modelos, db_session=db_session, usuario=usuario,
        )
        conteos["creados" if fila["accion"] == "crear" else "actualizados"] += 1
    return conteos


def exportar_excel_tabla(titulo, encabezados, filas):
    libro = Workbook(); hoja = libro.active; hoja.title = titulo[:31]; hoja.append(encabezados)
    for fila in filas: hoja.append(fila)
    if Font is not None and PatternFill is not None:
        for celda in hoja[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="176B89")
    hoja.freeze_panes = "A2"; salida = BytesIO(); libro.save(salida); salida.seek(0); return salida


def exportar_pdf_tabla(titulo, unidad, encabezados, filas):
    salida = BytesIO(); pdf = canvas.Canvas(salida, pagesize=landscape(A4)); _ancho, alto = landscape(A4); y = alto - 38
    pdf.setFont("Helvetica-Bold", 15); pdf.drawString(32, y, titulo); y -= 18
    pdf.setFont("Helvetica", 9); pdf.drawString(32, y, unidad); y -= 22
    anchos = [32 + indice * (770 / max(1, len(encabezados))) for indice in range(len(encabezados))]
    pdf.setFont("Helvetica-Bold", 7)
    for x, texto in zip(anchos, encabezados): pdf.drawString(x, y, str(texto)[:20])
    y -= 15; pdf.setFont("Helvetica", 7)
    if not filas: pdf.drawString(32, y, "Sin registros.")
    for fila in filas:
        if y < 35: pdf.showPage(); y = alto - 38
        for x, valor in zip(anchos, fila): pdf.drawString(x, y, str(valor or "")[:22])
        y -= 13
    pdf.save(); salida.seek(0); return salida
