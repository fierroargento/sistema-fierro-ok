"""Une archivos ML por seccion y genera lotes trazables, siempre en memoria."""

import csv
import hashlib
import json
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from services.certificacion_offline_mercado_libre import procesar_documento_publicaciones
from services.consolidacion_offline_ml import consolidar_snapshot_ml


SECCIONES = ("precios", "cargos", "envios", "promociones")
OBLIGATORIAS = ("precios", "cargos", "envios")
CONTRATO_LOTE = {
    "archivos_locales": True,
    "persistencia": False,
    "consultas_externas": False,
    "acciones_externas": False,
}


def _documento(contenido, seccion):
    if contenido in (None, b"", ""):
        return []
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8-sig")
    try:
        if isinstance(contenido, str):
            limpio = contenido.lstrip("\ufeff \t\r\n")
            if limpio.startswith(("[", "{")):
                datos = json.loads(limpio)
            else:
                datos = list(csv.DictReader(StringIO(limpio)))
        else:
            datos = contenido
    except (json.JSONDecodeError, UnicodeDecodeError, csv.Error) as error:
        raise ValueError(f"El archivo de {seccion} no contiene JSON o CSV UTF-8 valido.") from error
    if isinstance(datos, dict):
        datos = [datos]
    if not isinstance(datos, list):
        raise ValueError(f"La seccion {seccion} debe contener una lista JSON.")
    return datos


def _identidad(item, seccion, numero):
    if not isinstance(item, dict):
        raise ValueError(f"{seccion}, fila {numero}: cada registro debe ser un objeto.")
    referencia = str(item.get("publicacion_id") or item.get("id") or "").strip()
    if not referencia:
        raise ValueError(f"{seccion}, fila {numero}: falta publicacion_id.")
    return referencia


def _indexar(contenido, seccion):
    filas = _documento(contenido, seccion)
    indice, errores = {}, []
    for numero, item in enumerate(filas, start=1):
        try:
            referencia = _identidad(item, seccion, numero)
            if referencia in indice:
                raise ValueError(f"{seccion}, fila {numero}: publicacion duplicada.")
            indice[referencia] = dict(item)
        except ValueError as error:
            errores.append(str(error))
    return indice, errores


def preparar_lote_secciones(archivos, *, cuenta_codigo, organizacion_id, unidad_negocio_id):
    """Normaliza cuatro secciones sin escribirlas y devuelve un lote reproducible."""
    indices, errores, firmas = {}, [], {}
    for seccion in SECCIONES:
        indice, fallas = _indexar((archivos or {}).get(seccion), seccion)
        indices[seccion] = indice
        errores.extend(fallas)
        firmas[seccion] = hashlib.sha256(json.dumps(
            indice, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
    referencias = sorted(set().union(*(set(indice) for indice in indices.values())))
    combinadas = []
    for referencia in referencias:
        faltantes = [seccion for seccion in OBLIGATORIAS if referencia not in indices[seccion]]
        if faltantes:
            errores.append(f"{referencia}: faltan secciones obligatorias: {', '.join(faltantes)}.")
            continue
        precio = indices["precios"][referencia]
        cargo = indices["cargos"][referencia]
        envio = indices["envios"][referencia]
        promocion = indices["promociones"].get(referencia, {})
        sku = str(precio.get("seller_sku") or precio.get("sku") or "").strip()
        if not sku:
            errores.append(f"{referencia}: falta seller_sku en precios.")
            continue
        combinadas.append({
            "publicacion_id": referencia,
            "seller_sku": sku,
            "price": precio.get("price", precio.get("precio")),
            "original_price": (
                promocion.get("original_price")
                or promocion.get("precio_original")
                or precio.get("original_price")
                or precio.get("price", precio.get("precio"))
            ),
            "status": precio.get("status", precio.get("estado")),
            "listing_type_id": precio.get("listing_type_id", precio.get("tipo_publicacion")),
            "commission_percentage": cargo.get("commission_percentage", cargo.get("comision_pct")),
            "fixed_fee": cargo.get("fixed_fee", cargo.get("cargo_fijo", 0)),
            "shipping_cost": envio.get("shipping_cost", envio.get("costo_envio", 0)),
            "promotion_active": promocion.get("promotion_active", promocion.get("promocion_activa", False)),
        })
    snapshot = procesar_documento_publicaciones(
        combinadas, cuenta_codigo=cuenta_codigo,
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    )
    errores.extend(item["error"] for item in snapshot["errores"])
    material = {
        "cuenta_codigo": str(cuenta_codigo),
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "firmas_secciones": firmas,
        "referencias": referencias,
    }
    lote_id = hashlib.sha256(json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "lote_id": lote_id, "firmas_secciones": firmas,
        "cantidad_por_seccion": {clave: len(valor) for clave, valor in indices.items()},
        "snapshot": snapshot, "errores_lote": errores,
        "completas": len(combinadas), "referencias": len(referencias),
        "contrato": dict(CONTRATO_LOTE), "escrituras": 0, "acciones_externas": 0,
    }


def consolidar_lote_secciones(archivos, filas_control, *, cuenta_codigo,
                              organizacion_id, unidad_negocio_id, lista_precio_id):
    lote = preparar_lote_secciones(
        archivos, cuenta_codigo=cuenta_codigo,
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    )
    control = consolidar_snapshot_ml(
        lote["snapshot"], filas_control, lista_precio_id=lista_precio_id,
    )
    return {"lote": lote, "control": control, "aplicable": False}


def _csv_bytes(encabezados, ejemplo):
    texto = StringIO(newline="")
    escritor = csv.writer(texto)
    escritor.writerow(encabezados)
    escritor.writerow(ejemplo)
    return texto.getvalue().encode("utf-8-sig")


def plantillas_secciones_zip():
    archivos = {
        "01_precios.csv": (("publicacion_id", "seller_sku", "price", "status", "listing_type_id"), ("MLA-DEMO-001", "SKU-DEMO", 15000, "active", "gold_special")),
        "02_cargos.csv": (("publicacion_id", "commission_percentage", "fixed_fee"), ("MLA-DEMO-001", 15, 1200)),
        "03_envios.csv": (("publicacion_id", "shipping_cost"), ("MLA-DEMO-001", 3500)),
        "04_promociones.csv": (("publicacion_id", "promotion_active", "original_price"), ("MLA-DEMO-001", "false", 15000)),
    }
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as paquete:
        for nombre, (encabezados, ejemplo) in archivos.items():
            paquete.writestr(nombre, _csv_bytes(encabezados, ejemplo))
        paquete.writestr(
            "LEEME.txt",
            "Plantillas SaaS genericas. Cada archivo se importa por separado. "
            "Los importes se expresan en moneda, no en centavos. "
            "La promocion es opcional; las otras tres secciones son obligatorias.\n",
        )
    salida.seek(0)
    return salida


def exportar_lote_json(resultado):
    salida = BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str,
    ).encode("utf-8"))
    salida.seek(0)
    return salida
