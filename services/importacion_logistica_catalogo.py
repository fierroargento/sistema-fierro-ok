"""Importacion tenant de la ficha fisica y logistica de un catalogo.

No activa productos, no modifica precios y no consulta canales externos.
Los campos vacios no pisan datos existentes.
"""

from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook

from services.importacion_productos_costeo import normalizar


CAMPOS_LOGISTICA = {
    "catalogo_codigo": {
        "nombre": "Codigo de catalogo", "obligatorio": True,
        "alias": {"catalogo", "codigo catalogo", "codigo de catalogo"},
    },
    "sku_comercial": {
        "nombre": "SKU comercial", "obligatorio": True,
        "alias": {"sku", "sku comercial", "codigo producto"},
    },
    "peso_producto_gr": {
        "nombre": "Peso producto gr", "obligatorio": False,
        "alias": {"peso", "peso gr", "peso producto gr", "peso embalado"},
    },
    "largo_producto_cm": {
        "nombre": "Largo producto cm", "obligatorio": False,
        "alias": {"largo", "largo cm", "largo producto cm"},
    },
    "ancho_producto_cm": {
        "nombre": "Ancho producto cm", "obligatorio": False,
        "alias": {"ancho", "ancho cm", "ancho producto cm"},
    },
    "alto_producto_cm": {
        "nombre": "Alto producto cm", "obligatorio": False,
        "alias": {"alto", "alto cm", "alto producto cm"},
    },
    "material": {
        "nombre": "Material", "obligatorio": False, "alias": {"material"},
    },
    "color": {
        "nombre": "Color", "obligatorio": False, "alias": {"color"},
    },
    "terminacion": {
        "nombre": "Terminacion", "obligatorio": False,
        "alias": {"terminacion", "acabado"},
    },
    "contenido_paquete": {
        "nombre": "Contenido del paquete", "obligatorio": False,
        "alias": {"contenido", "contenido paquete", "contenido del paquete"},
    },
}

NUMERICOS_LOGISTICA = {
    "peso_producto_gr", "largo_producto_cm", "ancho_producto_cm",
    "alto_producto_cm",
}


def sugerir_mapeo_logistica(encabezados):
    resultado, usados = {}, set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(encabezado)
        destino = ""
        for campo, definicion in CAMPOS_LOGISTICA.items():
            if campo not in usados and limpio in definicion["alias"]:
                destino = campo
                usados.add(campo)
                break
        resultado[str(indice)] = destino
    return resultado


def validar_mapeo_logistica(mapeo):
    destinos = [campo for campo in mapeo.values() if campo]
    if len(destinos) != len(set(destinos)):
        raise ValueError("Un campo del sistema no puede recibir dos columnas.")
    faltantes = [
        definicion["nombre"]
        for campo, definicion in CAMPOS_LOGISTICA.items()
        if definicion["obligatorio"] and campo not in destinos
    ]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")
    if not any(campo in destinos for campo in set(CAMPOS_LOGISTICA) - {
        "catalogo_codigo", "sku_comercial",
    }):
        raise ValueError("Mapeá al menos un dato físico o descriptivo.")


def _extraer(fila, mapeo):
    return {
        campo: fila["valores"][int(indice)]
        if int(indice) < len(fila["valores"]) else ""
        for indice, campo in mapeo.items() if campo
    }


def _decimal_positivo(valor, nombre, errores):
    texto = str(valor or "").strip()
    if not texto:
        return None
    normalizado = texto.replace(" ", "")
    if "," in normalizado and "." in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    else:
        normalizado = normalizado.replace(",", ".")
    try:
        numero = Decimal(normalizado)
    except InvalidOperation:
        errores.append(f"{nombre} no es valido")
        return None
    if numero <= 0:
        errores.append(f"{nombre} debe ser mayor a cero")
        return None
    return str(numero)


def _numeros_equivalentes(actual, nuevo):
    try:
        return Decimal(str(actual)) == Decimal(str(nuevo))
    except (InvalidOperation, TypeError, ValueError):
        return False


def previsualizar_logistica(
    filas, mapeo, *, organizacion_id, unidad_negocio_id, modelos,
):
    validar_mapeo_logistica(mapeo)
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    resultado, identidades = [], set()
    nombres = {
        campo: definicion["nombre"] for campo, definicion in CAMPOS_LOGISTICA.items()
    }
    for fila in filas:
        datos = _extraer(fila, mapeo)
        catalogo_codigo = str(datos.get("catalogo_codigo") or "").strip().lower()
        sku = str(datos.get("sku_comercial") or "").strip().upper()
        errores = []
        if not catalogo_codigo:
            errores.append("Falta codigo de catalogo")
        if not sku:
            errores.append("Falta SKU comercial")
        identidad = (catalogo_codigo, sku)
        if all(identidad):
            if identidad in identidades:
                errores.append("El archivo contiene una fila duplicada")
            identidades.add(identidad)

        catalogo = None
        inclusion = None
        if not errores:
            catalogo = Catalogo.query.filter_by(
                organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_negocio_id,
                codigo=catalogo_codigo,
            ).first()
            if catalogo is None:
                errores.append("No existe el catalogo en la unidad activa")
        if not errores:
            opciones = CatalogoProducto.query.filter(
                CatalogoProducto.catalogo_id == catalogo.id,
                CatalogoProducto.sku_comercial.ilike(sku),
            ).all()
            if len(opciones) != 1:
                errores.append("No se encontro una unica inclusion para el SKU")
            else:
                inclusion = opciones[0]

        cambios = {}
        for campo in set(CAMPOS_LOGISTICA) - {
            "catalogo_codigo", "sku_comercial",
        }:
            valor_crudo = datos.get(campo)
            if str(valor_crudo or "").strip() == "":
                continue
            if campo in NUMERICOS_LOGISTICA:
                valor = _decimal_positivo(valor_crudo, nombres[campo], errores)
            else:
                valor = str(valor_crudo).strip()[:500]
            if valor is not None:
                actual = getattr(inclusion, campo, None) if inclusion else None
                iguales = (
                    _numeros_equivalentes(actual, valor)
                    if campo in NUMERICOS_LOGISTICA and actual is not None
                    else str(actual or "").strip() == str(valor).strip()
                )
                if not iguales:
                    cambios[campo] = valor

        if errores:
            accion = "rechazado"
        elif cambios:
            accion = "actualizar"
        else:
            accion = "sin_cambios"
        resultado.append({
            "numero": fila["numero"],
            "catalogo_codigo": catalogo_codigo,
            "sku_comercial": sku,
            "inclusion_id": getattr(inclusion, "id", None),
            "cambios": cambios,
            "accion": accion,
            "errores": errores,
        })
    return resultado


def aplicar_logistica(
    vista, *, organizacion_id, unidad_negocio_id, modelos, db_session,
):
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    conteos = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "rechazados": 0}
    try:
        for fila in vista:
            if fila["accion"] == "rechazado":
                conteos["rechazados"] += 1
                continue
            if fila["accion"] == "sin_cambios":
                conteos["sin_cambios"] += 1
                continue
            inclusion = CatalogoProducto.query.join(Catalogo).filter(
                CatalogoProducto.id == fila["inclusion_id"],
                Catalogo.organizacion_id == organizacion_id,
                Catalogo.unidad_negocio_id == unidad_negocio_id,
            ).first()
            if inclusion is None:
                raise ValueError("La inclusion cambio desde la validacion.")
            for campo, valor in fila["cambios"].items():
                setattr(inclusion, campo, valor)
            conteos["actualizados"] += 1
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return conteos


def plantilla_logistica_catalogo():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Ficha fisica"
    hoja.append([d["nombre"].upper() for d in CAMPOS_LOGISTICA.values()])
    hoja.append([
        "catalogo-fierro", "PP6040H", 3200, 36, 42, 5,
        "Acero", "Negro", "Pintura alta temperatura", "1 parrilla",
    ])
    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
