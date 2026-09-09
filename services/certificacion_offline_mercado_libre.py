"""Certifica snapshots comerciales de Mercado Libre sin consultar ni modificar el canal."""

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO


EFECTOS_BLOQUEADOS = {
    "consulta_api": False,
    "oauth": False,
    "webhooks": False,
    "persistencia": False,
    "cancelacion_promociones": False,
    "actualizacion_precios": False,
}


def _centavos(valor, campo, *, obligatorio=True):
    if valor in (None, ""):
        if obligatorio:
            raise ValueError(f"Falta {campo}.")
        return 0
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{campo} no es valido.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"{campo} no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _porcentaje(valor):
    try:
        numero = Decimal(str(valor or 0).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("La comision porcentual no es valida.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100:
        raise ValueError("La comision debe estar entre 0 y menos de 100.")
    return numero


def _texto(item, *campos):
    for campo in campos:
        valor = item.get(campo)
        if valor not in (None, ""):
            return str(valor).strip()
    return ""


def normalizar_publicacion(item, *, cuenta_codigo, organizacion_id, unidad_negocio_id):
    if not isinstance(item, dict):
        raise ValueError("Cada publicacion debe ser un objeto JSON.")
    publicacion_id = _texto(item, "publicacion_id", "id")
    sku = _texto(item, "sku", "seller_sku")
    if not publicacion_id:
        raise ValueError("Falta publicacion_id.")
    if not sku:
        raise ValueError("Falta seller_sku.")
    precio = _centavos(item.get("precio", item.get("price")), "precio")
    original = _centavos(
        item.get("precio_original", item.get("original_price", item.get("precio", item.get("price")))),
        "precio_original",
    )
    porcentaje = _porcentaje(item.get("comision_pct", item.get("commission_percentage", 0)))
    comision = int((Decimal(precio) * porcentaje / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    cargo_fijo = _centavos(item.get("cargo_fijo", item.get("fixed_fee", 0)), "cargo_fijo", obligatorio=False)
    envio = _centavos(item.get("costo_envio", item.get("shipping_cost", 0)), "costo_envio", obligatorio=False)
    piso = _centavos(
        item.get("piso_economico", item.get("economic_floor", 0)),
        "piso_economico", obligatorio=False,
    )
    precio_seguro = _centavos(
        item.get("precio_seguro", item.get("proposed_safe_price", item.get("precio", item.get("price")))),
        "precio_seguro",
    )
    promocion = item.get("promocion") or {}
    valor_promocion = item.get(
        "promocion_activa",
        item.get("promotion_active", promocion.get("activa", False)),
    )
    promo_activa = (
        valor_promocion.strip().lower() in {"1", "true", "si", "activa", "active"}
        if isinstance(valor_promocion, str) else bool(valor_promocion)
    )
    liquidacion = precio - comision - cargo_fijo - envio
    diferencia = liquidacion - piso
    riesgo_promo = promo_activa and precio_seguro > precio
    acciones = []
    if diferencia < 0 or precio_seguro > precio:
        if riesgo_promo:
            acciones.append({"orden": 1, "accion": "cancelar_promocion_manual", "ejecutada": False})
        acciones.append({
            "orden": len(acciones) + 1,
            "accion": "actualizar_precio_manual",
            "precio_objetivo_centavos": precio_seguro,
            "depende_de": "cancelar_promocion_manual" if riesgo_promo else None,
            "ejecutada": False,
        })
    identidad = f"{cuenta_codigo}:{publicacion_id}"
    return {
        "identidad": identidad,
        "cuenta_codigo": str(cuenta_codigo),
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "publicacion_id": publicacion_id,
        "sku": sku.upper(),
        "estado": _texto(item, "estado", "status"),
        "tipo_publicacion": _texto(item, "tipo_publicacion", "listing_type_id"),
        "precio_centavos": precio,
        "precio_original_centavos": original,
        "comision_pct": str(porcentaje),
        "comision_centavos": comision,
        "cargo_fijo_centavos": cargo_fijo,
        "envio_centavos": envio,
        "liquidacion_centavos": liquidacion,
        "piso_economico_centavos": piso,
        "diferencia_centavos": diferencia,
        "precio_seguro_centavos": precio_seguro,
        "promocion_activa": promo_activa,
        "riesgo_recalculo_promocion": riesgo_promo,
        "cumple_piso": diferencia >= 0,
        "acciones_proyectadas": acciones,
    }


def procesar_documento_publicaciones(contenido, *, cuenta_codigo, organizacion_id, unidad_negocio_id):
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8-sig")
    try:
        documento = json.loads(contenido) if isinstance(contenido, str) else contenido
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("El archivo no contiene JSON UTF-8 valido.") from error
    filas = documento if isinstance(documento, list) else [documento]
    resultados, errores, vistos = [], [], set()
    for numero, item in enumerate(filas, start=1):
        try:
            normalizado = normalizar_publicacion(
                item, cuenta_codigo=cuenta_codigo,
                organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            )
            if normalizado["identidad"] in vistos:
                raise ValueError("La publicacion esta duplicada dentro del archivo.")
            vistos.add(normalizado["identidad"])
            resultados.append({"numero": numero, **normalizado})
        except (ValueError, TypeError) as error:
            errores.append({"numero": numero, "error": str(error)})
    resumen = {
        "filas": len(filas),
        "validas": len(resultados),
        "errores": len(errores),
        "rentables": sum(item["cumple_piso"] for item in resultados),
        "debajo_piso": sum(not item["cumple_piso"] for item in resultados),
        "promociones_riesgosas": sum(item["riesgo_recalculo_promocion"] for item in resultados),
        "acciones_proyectadas": sum(len(item["acciones_proyectadas"]) for item in resultados),
    }
    evidencia = {"resultados": resultados, "errores": errores, "resumen": resumen}
    firma = hashlib.sha256(json.dumps(
        evidencia, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        **evidencia, "firma_evidencia": firma,
        "modo": "mercado_libre_offline", "efectos": dict(EFECTOS_BLOQUEADOS),
        "acciones_externas": 0, "escrituras": 0, "aplicable": False,
    }


def certificar_publicaciones_offline():
    casos = [
        {"codigo": "rentable", "item": {"id": "MLA-1", "seller_sku": "A", "price": 40000, "commission_percentage": 15, "fixed_fee": 0, "shipping_cost": 5000, "economic_floor": 28000}, "estado": True, "acciones": 0},
        {"codigo": "cargo_fijo", "item": {"id": "MLA-2", "seller_sku": "B", "price": 30000, "commission_percentage": 15, "fixed_fee": 1500, "shipping_cost": 0, "economic_floor": 22000}, "estado": True, "acciones": 0},
        {"codigo": "debajo_piso", "item": {"id": "MLA-3", "seller_sku": "C", "price": 1000, "commission_percentage": 15, "fixed_fee": 200, "economic_floor": 900, "proposed_safe_price": 1300}, "estado": False, "acciones": 1},
        {"codigo": "promo_bloqueante", "item": {"id": "MLA-4", "seller_sku": "D", "price": 1000, "original_price": 1100, "commission_percentage": 15, "fixed_fee": 100, "economic_floor": 900, "proposed_safe_price": 1200, "promotion_active": True}, "estado": False, "acciones": 2},
    ]
    resultados = []
    for caso in casos:
        salida = normalizar_publicacion(
            caso["item"], cuenta_codigo="CUENTA-DEMO",
            organizacion_id=1, unidad_negocio_id=1,
        )
        cumple = salida["cumple_piso"] is caso["estado"] and len(salida["acciones_proyectadas"]) == caso["acciones"]
        resultados.append({"codigo": caso["codigo"], "cumple": cumple, "resultado": salida})
    return {
        "aprobada": all(item["cumple"] for item in resultados),
        "total": len(resultados), "aprobados": sum(item["cumple"] for item in resultados),
        "resultados": resultados, "acciones_externas": 0, "escrituras": 0,
        "efectos": dict(EFECTOS_BLOQUEADOS),
    }


def exportar_json(resultado):
    salida = BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
    salida.seek(0)
    return salida
