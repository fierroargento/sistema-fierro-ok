"""Previsualiza borradores fiscales desde CSV sin persistir ni emitir."""

import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ALIASES = {
    "referencia": {"referencia", "comprobante", "id comprobante", "lote"},
    "entidad": {"entidad fiscal", "entidad_fiscal", "cuit emisor", "cuit_emisor"},
    "punto": {"punto de venta", "punto_venta", "pv"},
    "tipo": {"tipo comprobante", "tipo_comprobante", "codigo arca", "codigo_arca"},
    "receptor": {"receptor", "cliente", "razon social", "razon_social"},
    "documento": {"documento", "dni", "cuit receptor", "cuit_receptor"},
    "condicion_iva": {"condicion iva", "condicion_iva"},
    "descripcion": {"descripcion", "producto", "detalle"},
    "sku": {"sku", "codigo producto", "codigo_producto"},
    "cantidad": {"cantidad", "unidades"},
    "precio": {"precio unitario", "precio_unitario", "precio final", "precio"},
    "iva": {"iva", "alicuota iva", "alicuota_iva"},
}


def _normalizar(valor):
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).replace("_", " ").split())


def _leer(contenido):
    if len(contenido or b"") > 2_000_000:
        raise ValueError("El archivo supera el límite de 2 MB.")
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return (contenido or b"").decode(codificacion)
        except UnicodeDecodeError:
            pass
    raise ValueError("No se pudo leer la codificación del archivo.")


def _columnas(encabezados):
    resultado = {}
    for indice, encabezado in enumerate(encabezados or []):
        limpio = _normalizar(encabezado)
        for campo, aliases in ALIASES.items():
            if campo not in resultado and limpio in {_normalizar(a) for a in aliases}:
                resultado[campo] = indice
    faltantes = [c for c in ("referencia", "entidad", "punto", "tipo", "receptor", "descripcion", "cantidad", "precio", "iva") if c not in resultado]
    if faltantes:
        raise ValueError("Faltan columnas: " + ", ".join(faltantes) + ".")
    return resultado


def _decimal(valor, nombre):
    texto = str(valor or "").strip().replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation as error:
        raise ValueError(f"{nombre} no es válido.") from error


def _centavos(valor):
    importe = _decimal(valor, "El precio")
    if importe < 0:
        raise ValueError("El precio no puede ser negativo.")
    return int((importe * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _milesimas(valor):
    cantidad = _decimal(valor, "La cantidad")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    return int((cantidad * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _basis_points(valor):
    iva = _decimal(valor, "La alícuota IVA")
    if iva < 0 or iva > 100:
        raise ValueError("La alícuota IVA no es válida.")
    return int((iva * 100).quantize(Decimal("1")))


def _calcular(cantidad_milesimas, precio_centavos, iva_bp):
    total = int((Decimal(precio_centavos) * cantidad_milesimas / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    neto = int((Decimal(total) / (Decimal("1") + Decimal(iva_bp) / 10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return neto, total - neto, total


def previsualizar_borradores(contenido, *, organizacion_id, entidades, puntos, tipos, referencias_existentes=()):
    """Construye un plan inmutable; no recibe sesión de base de datos."""
    texto = _leer(contenido)
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except csv.Error as error:
        raise ValueError("No se pudo reconocer el separador del archivo.") from error
    lector = csv.reader(io.StringIO(texto), dialecto)
    columnas = _columnas(next(lector, None))
    entidades_tenant = {str(e.cuit or "").strip(): e for e in entidades if e.organizacion_id == organizacion_id}
    puntos_tenant = {(p.entidad_fiscal_id, int(p.numero)): p for p in puntos if p.organizacion_id == organizacion_id}
    tipos_tenant = {(t.punto_venta_fiscal_id, int(t.codigo_arca)): t for t in tipos if getattr(getattr(t, "punto_venta", None), "organizacion_id", None) == organizacion_id}
    existentes = {str(x) for x in referencias_existentes if x}
    grupos, orden = {}, []
    for numero, valores in enumerate(lector, 2):
        if not any(str(v).strip() for v in valores):
            continue
        if sum(len(str(v)) for v in valores) > 5000:
            raise ValueError(f"La fila {numero} supera el tamaño permitido.")
        def valor(campo):
            indice = columnas.get(campo)
            return valores[indice].strip() if indice is not None and indice < len(valores) else ""
        referencia = valor("referencia")[:150]
        if referencia not in grupos:
            grupos[referencia] = {"referencia": referencia, "filas": [], "errores": []}; orden.append(referencia)
        grupo = grupos[referencia]; errores = []
        entidad = entidades_tenant.get(valor("entidad"))
        try: punto_numero = int(valor("punto")); tipo_codigo = int(valor("tipo"))
        except ValueError: punto_numero = tipo_codigo = -1; errores.append("Punto de venta o tipo inválido")
        punto = puntos_tenant.get((getattr(entidad, "id", None), punto_numero))
        tipo = tipos_tenant.get((getattr(punto, "id", None), tipo_codigo))
        if not referencia: errores.append("Falta la referencia del comprobante")
        if referencia in existentes: errores.append("La referencia ya existe en el tenant")
        if entidad is None: errores.append("La entidad fiscal no pertenece al tenant")
        if punto is None: errores.append("El punto de venta no pertenece a la entidad")
        if tipo is None: errores.append("El tipo no pertenece al punto de venta")
        if not valor("receptor"): errores.append("Falta el receptor")
        if not valor("descripcion"): errores.append("Falta la descripción")
        try:
            cantidad = _milesimas(valor("cantidad")); precio = _centavos(valor("precio")); iva_bp = _basis_points(valor("iva")); neto, iva, total = _calcular(cantidad, precio, iva_bp)
        except ValueError as error:
            cantidad = precio = iva_bp = neto = iva = total = 0; errores.append(str(error))
        cabecera = (getattr(entidad, "id", None), getattr(punto, "id", None), getattr(tipo, "id", None), valor("receptor"), valor("documento"), valor("condicion_iva"))
        if grupo["filas"] and grupo["cabecera"] != cabecera: errores.append("La cabecera cambia dentro del mismo comprobante")
        grupo.setdefault("cabecera", cabecera)
        fila = {"numero": numero, "descripcion": valor("descripcion")[:300], "sku": valor("sku")[:100], "cantidad_milesimas": cantidad, "precio_unitario_centavos": precio, "alicuota_iva_basis_points": iva_bp, "neto_centavos": neto, "iva_centavos": iva, "total_centavos": total, "errores": errores}
        grupo["filas"].append(fila); grupo["errores"].extend(f"Fila {numero}: {e}" for e in errores)
        if len(grupo["filas"]) > 200: raise ValueError("Un comprobante supera las 200 líneas.")
    if not orden: raise ValueError("El archivo no contiene datos.")
    if len(orden) > 200: raise ValueError("El archivo supera los 200 comprobantes.")
    vistos = set(); comprobantes = []
    for referencia in orden:
        grupo = grupos[referencia]
        if referencia in vistos: grupo["errores"].append("Referencia duplicada")
        vistos.add(referencia)
        entidad_id, punto_id, tipo_id, receptor, documento, condicion = grupo.pop("cabecera")
        grupo.update({"entidad_fiscal_id": entidad_id, "punto_venta_fiscal_id": punto_id, "tipo_comprobante_fiscal_id": tipo_id, "receptor_nombre": receptor[:200], "receptor_documento": documento[:30], "receptor_condicion_iva": condicion[:80], "estado": "rechazado" if grupo["errores"] else "preparado", "neto_centavos": sum(f["neto_centavos"] for f in grupo["filas"]), "iva_centavos": sum(f["iva_centavos"] for f in grupo["filas"]), "total_centavos": sum(f["total_centavos"] for f in grupo["filas"])})
        comprobantes.append(grupo)
    resumen = {"comprobantes": len(comprobantes), "lineas": sum(len(c["filas"]) for c in comprobantes), "preparados": sum(c["estado"] == "preparado" for c in comprobantes), "rechazados": sum(c["estado"] == "rechazado" for c in comprobantes), "acciones_externas": 0, "escrituras": 0}
    base = {"organizacion_id": organizacion_id, "huella_documento": hashlib.sha256(contenido).hexdigest(), "resumen": resumen, "comprobantes": comprobantes, "emision_real": False}
    base["huella_plan"] = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return base


def exportar_previsualizacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
