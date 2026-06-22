"""
Servicio de catálogo de productos.

Centraliza la lectura y normalización del Excel maestro de productos.
No depende de Flask ni de app.py.
"""

import math
import re

import pandas as pd


ALIASES_COLUMNAS_PRODUCTO = {
    "sku": ["sku", "codigo", "código", "codigo sku", "código sku", "cod", "cód"],
    "descripcion": ["descripcion", "descripción", "producto", "nombre", "detalle"],
    "peso_gr": ["peso gr", "peso gramos", "peso g", "peso_gr", "peso"],
    "alto_cm": ["alto cm", "alto_cm", "alto"],
    "ancho_cm": ["ancho cm", "ancho_cm", "ancho"],
    "largo_cm": ["largo cm", "largo_cm", "largo", "profundidad"],
    "permite_correo": ["permite correo", "permite_correo", "correo", "correo argentino"],
    "permite_via_cargo": ["permite via cargo", "permite vía cargo", "permite_via_cargo", "via cargo", "vía cargo"],
    "requiere_revision_logistica": [
        "requiere revision logistica",
        "requiere revisión logística",
        "requiere_revision_logistica",
        "revision logistica",
        "revisión logística",
    ],
    "observacion_logistica": [
        "observacion logistica",
        "observación logística",
        "observaciones logistica",
        "observaciones logística",
        "observacion",
        "observación",
    ],
}


def valor_vacio(valor):
    if valor is None:
        return True

    if isinstance(valor, str):
        return valor.strip() == ""

    if isinstance(valor, bool):
        return False

    if isinstance(valor, float) and math.isnan(valor):
        return True

    try:
        if valor is pd.NA:
            return True
    except Exception:
        pass

    return False


def normalizar_columna_producto(nombre):
    texto = str(nombre or "").strip().lower()

    for origen, destino in {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }.items():
        texto = texto.replace(origen, destino)

    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


def normalizar_sku_producto(valor):
    if valor_vacio(valor):
        return ""

    return str(valor).strip().upper()


def texto_producto(valor):
    if valor_vacio(valor):
        return ""

    return str(valor).strip()


def numero_producto(valor):
    if valor_vacio(valor):
        return None

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    texto = str(valor).strip().lower()

    texto = (
        texto
        .replace("kilogramos", "kg")
        .replace("kilogramo", "kg")
        .replace("gramos", "")
        .replace("centimetros", "")
        .replace("centímetros", "")
        .replace("cm", "")
        .replace("gr", "")
    )

    texto = re.sub(r"[^0-9,\.\-]", "", texto)

    if not texto:
        return None

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


def peso_gr_producto(valor):
    if valor_vacio(valor):
        return None

    texto_original = str(valor).strip().lower()
    numero = numero_producto(valor)

    if numero is None:
        return None

    if "kg" in texto_original or "kilo" in texto_original:
        return numero * 1000

    return numero


def bool_producto(valor, default=False):
    if valor_vacio(valor):
        return default

    texto = str(valor).strip().lower()

    for origen, destino in {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
    }.items():
        texto = texto.replace(origen, destino)

    if texto in {"1", "si", "s", "true", "verdadero", "yes", "y", "x", "ok"}:
        return True

    if texto in {"0", "no", "n", "false", "falso"}:
        return False

    return default


def _mapear_columnas_excel(df):
    return {
        normalizar_columna_producto(col): col
        for col in df.columns
    }


def _valor_por_alias_dict(registro, columnas, campo, fallback_index=None):
    aliases = ALIASES_COLUMNAS_PRODUCTO.get(campo, [])

    for alias in aliases:
        columna = columnas.get(normalizar_columna_producto(alias))
        if columna is not None:
            return registro.get(columna)

    if fallback_index is not None:
        valores = list(registro.values())
        if fallback_index < len(valores):
            return valores[fallback_index]

    return None


def normalizar_producto_catalogo(datos):
    datos = datos or {}

    return {
        "sku": normalizar_sku_producto(datos.get("sku")),
        "descripcion": texto_producto(datos.get("descripcion")),
        "peso_gr": peso_gr_producto(datos.get("peso_gr")),
        "alto_cm": numero_producto(datos.get("alto_cm")),
        "ancho_cm": numero_producto(datos.get("ancho_cm")),
        "largo_cm": numero_producto(datos.get("largo_cm")),
        "permite_correo": bool_producto(datos.get("permite_correo"), default=True),
        "permite_via_cargo": bool_producto(datos.get("permite_via_cargo"), default=True),
        "requiere_revision_logistica": bool_producto(datos.get("requiere_revision_logistica"), default=False),
        "observacion_logistica": texto_producto(datos.get("observacion_logistica"))[:300],
    }


def validar_producto_catalogo(producto):
    errores = []

    if not producto.get("sku"):
        errores.append("El SKU es obligatorio.")

    if not producto.get("descripcion"):
        errores.append("La descripción es obligatoria.")

    for campo in ["peso_gr", "alto_cm", "ancho_cm", "largo_cm"]:
        valor = producto.get(campo)
        if valor is not None and valor <= 0:
            errores.append(f"{campo} debe ser mayor a cero.")

    return errores


def productos_desde_dataframe_catalogo(df):
    columnas = _mapear_columnas_excel(df)

    productos = []

    for registro in df.to_dict(orient="records"):
        datos = {
            "sku": _valor_por_alias_dict(registro, columnas, "sku", fallback_index=0),
            "descripcion": _valor_por_alias_dict(registro, columnas, "descripcion", fallback_index=1),
            "peso_gr": _valor_por_alias_dict(registro, columnas, "peso_gr"),
            "alto_cm": _valor_por_alias_dict(registro, columnas, "alto_cm"),
            "ancho_cm": _valor_por_alias_dict(registro, columnas, "ancho_cm"),
            "largo_cm": _valor_por_alias_dict(registro, columnas, "largo_cm"),
            "permite_correo": _valor_por_alias_dict(registro, columnas, "permite_correo"),
            "permite_via_cargo": _valor_por_alias_dict(registro, columnas, "permite_via_cargo"),
            "requiere_revision_logistica": _valor_por_alias_dict(registro, columnas, "requiere_revision_logistica"),
            "observacion_logistica": _valor_por_alias_dict(registro, columnas, "observacion_logistica"),
        }

        producto = normalizar_producto_catalogo(datos)

        if producto["sku"] or producto["descripcion"]:
            productos.append(producto)

    return productos


def productos_desde_excel_catalogo(archivo_excel):
    df = pd.read_excel(archivo_excel)
    return productos_desde_dataframe_catalogo(df)


def producto_desde_form_catalogo(form):
    """
    Convierte un formulario Admin en datos normalizados de producto.

    APB:
    - Los checkboxes HTML no vienen en request.form cuando están destildados.
    - Por eso acá convertimos explícitamente a "1" / "0".
    """

    form = form or {}

    return normalizar_producto_catalogo({
        "sku": form.get("sku"),
        "descripcion": form.get("descripcion"),
        "peso_gr": form.get("peso_gr"),
        "alto_cm": form.get("alto_cm"),
        "ancho_cm": form.get("ancho_cm"),
        "largo_cm": form.get("largo_cm"),
        "permite_correo": "1" if form.get("permite_correo") else "0",
        "permite_via_cargo": "1" if form.get("permite_via_cargo") else "0",
        "requiere_revision_logistica": "1" if form.get("requiere_revision_logistica") else "0",
        "observacion_logistica": form.get("observacion_logistica"),
    })


def producto_a_dict_catalogo(producto):
    """
    Convierte un modelo Producto en dict simple para templates o servicios.
    """

    if not producto:
        return {}

    return {
        "id": getattr(producto, "id", None),
        "sku": getattr(producto, "sku", "") or "",
        "descripcion": getattr(producto, "descripcion", "") or "",
        "peso_gr": getattr(producto, "peso_gr", None),
        "alto_cm": getattr(producto, "alto_cm", None),
        "ancho_cm": getattr(producto, "ancho_cm", None),
        "largo_cm": getattr(producto, "largo_cm", None),
        "permite_correo": True if getattr(producto, "permite_correo", True) is None else bool(getattr(producto, "permite_correo", True)),
        "permite_via_cargo": True if getattr(producto, "permite_via_cargo", True) is None else bool(getattr(producto, "permite_via_cargo", True)),
        "requiere_revision_logistica": bool(getattr(producto, "requiere_revision_logistica", False)),
        "observacion_logistica": getattr(producto, "observacion_logistica", "") or "",
    }


def producto_tiene_logistica_completa(producto):
    datos = producto_a_dict_catalogo(producto)

    return bool(
        datos.get("peso_gr")
        and datos.get("alto_cm")
        and datos.get("ancho_cm")
        and datos.get("largo_cm")
    )
