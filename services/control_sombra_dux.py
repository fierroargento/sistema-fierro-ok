"""Comparacion offline DUX/Fierro; nunca conecta ni persiste."""

import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation


ALIAS = {
    "sku": {"sku", "codigo", "código", "cod_producto", "codigo_producto"},
    "nombre": {"nombre", "producto", "descripcion", "descripción"},
    "stock": {"stock", "existencia", "cantidad", "stock_actual"},
    "precio": {"precio", "precio_venta", "precio_final", "pvp"},
}


def _texto(valor):
    return str(valor or "").strip()


def _clave(valor):
    return _texto(valor).lower().replace(" ", "_")


def _decimal(valor):
    texto = _texto(valor).replace("$", "").replace(" ", "")
    if not texto:
        return None
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation as error:
        raise ValueError(f"Importe o cantidad invalida: {valor}") from error


def leer_exportacion_dux(archivo, limite=20000):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    if not contenido:
        raise ValueError("El archivo DUX esta vacio.")
    if len(contenido) > 8 * 1024 * 1024:
        raise ValueError("El archivo DUX supera 8 MB.")
    texto = None
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ValueError("No se pudo leer la codificacion del CSV.")
    muestra = texto[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=";,\t")
    except csv.Error:
        dialecto = csv.excel
        dialecto.delimiter = ";"
    lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)
    if not lector.fieldnames:
        raise ValueError("El CSV no contiene encabezados.")
    columnas = {}
    for original in lector.fieldnames:
        normalizada = _clave(original)
        for destino, alias in ALIAS.items():
            if normalizada in alias and destino not in columnas:
                columnas[destino] = original
    if "sku" not in columnas:
        raise ValueError("El CSV debe incluir una columna SKU o Codigo.")
    filas = []
    vistos = set()
    for numero, fila in enumerate(lector, 2):
        if len(filas) >= limite:
            raise ValueError(f"El CSV supera el limite de {limite} productos.")
        sku = _texto(fila.get(columnas["sku"])).upper()
        if not sku:
            continue
        if sku in vistos:
            raise ValueError(f"SKU duplicado en DUX: {sku} (fila {numero}).")
        vistos.add(sku)
        stock = _decimal(fila.get(columnas.get("stock", "")))
        precio = _decimal(fila.get(columnas.get("precio", "")))
        filas.append({
            "sku": sku,
            "nombre": _texto(fila.get(columnas.get("nombre", ""))),
            "stock": int(stock) if stock is not None else None,
            "precio_centavos": int((precio * 100).quantize(Decimal("1"))) if precio is not None else None,
        })
    if not filas:
        raise ValueError("El CSV no contiene productos con SKU.")
    return filas


def construir_fotografia_fierro(*, items, existencias, productos_catalogo):
    catalogos = {int(p.id): p for p in productos_catalogo}
    stock_por_item = {}
    for existencia in existencias:
        item_id = int(getattr(existencia, "item_inventario_id", 0) or 0)
        stock_por_item[item_id] = stock_por_item.get(item_id, 0) + int(
            getattr(existencia, "stock_actual", 0) or 0
        )
    resultado = []
    for item in items:
        catalogo = catalogos.get(int(getattr(item, "catalogo_producto_id", 0) or 0))
        resultado.append({
            "sku": _texto(getattr(item, "sku", "")).upper(),
            "nombre": _texto(getattr(item, "nombre", "")),
            "stock": stock_por_item.get(int(item.id), 0),
            "precio_centavos": int(getattr(catalogo, "precio_centavos", 0) or 0) if catalogo else None,
            "activo": bool(getattr(item, "activo", False)),
        })
    return resultado


def comparar_sombra_dux(*, organizacion_id, dux, fierro, tolerancia_precio_centavos=1):
    por_dux = {fila["sku"]: fila for fila in dux}
    por_fierro = {fila["sku"]: fila for fila in fierro if fila["sku"]}
    detalles = []
    for sku in sorted(set(por_dux) | set(por_fierro)):
        origen = por_dux.get(sku)
        destino = por_fierro.get(sku)
        diferencias = []
        if origen is None:
            diferencias.append("solo_fierro")
        elif destino is None:
            diferencias.append("falta_fierro")
        else:
            if origen["stock"] is not None and origen["stock"] != destino["stock"]:
                diferencias.append("stock")
            if (
                origen["precio_centavos"] is not None
                and destino["precio_centavos"] is not None
                and abs(origen["precio_centavos"] - destino["precio_centavos"]) > tolerancia_precio_centavos
            ):
                diferencias.append("precio")
            if not destino.get("activo"):
                diferencias.append("inactivo_fierro")
        detalles.append({
            "sku": sku,
            "nombre": (origen or destino or {}).get("nombre", ""),
            "stock_dux": origen.get("stock") if origen else None,
            "stock_fierro": destino.get("stock") if destino else None,
            "precio_dux_centavos": origen.get("precio_centavos") if origen else None,
            "precio_fierro_centavos": destino.get("precio_centavos") if destino else None,
            "diferencias": diferencias,
            "coincide": not diferencias,
        })
    resumen = {
        "productos_dux": len(dux),
        "productos_fierro": len(fierro),
        "coincidentes": sum(1 for fila in detalles if fila["coincide"]),
        "observados": sum(1 for fila in detalles if not fila["coincide"]),
    }
    base = {
        "tipo": "control_sombra_dux",
        "version": 1,
        "organizacion_id": int(organizacion_id),
        "solo_lectura": True,
        "conexiones_externas": 0,
        "publicaciones": 0,
        "resumen": resumen,
        "listo_para_reemplazo": resumen["observados"] == 0 and bool(detalles),
        "detalles": detalles,
    }
    canonico = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    base["huella_sha256"] = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    return base


def exportar_control(resultado):
    contenido = json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8")
    return io.BytesIO(contenido)
