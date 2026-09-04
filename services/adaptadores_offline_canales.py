"""Adapta fixtures JSON locales al contrato interno de eventos comerciales."""

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


ADAPTADORES = {
    "mercado_libre": {"publicacion", "venta", "devolucion"},
    "mercado_pago": {"pago", "devolucion"},
    "tienda_nube": {"venta", "devolucion"},
}
ORDEN_EVENTOS = {"publicacion": 10, "comision": 20, "envio": 30, "promocion": 40, "venta": 50, "pago": 60, "devolucion": 70}


def _centavos(valor, nombre):
    try: numero = Decimal(str(0 if valor is None else valor).replace(",", "."))
    except InvalidOperation as error: raise ValueError(f"{nombre} no es valido.") from error
    if not numero.is_finite() or numero < 0: raise ValueError(f"{nombre} no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _requerir(payload, campo):
    valor = payload
    for parte in campo.split("."):
        if not isinstance(valor, dict) or parte not in valor: raise ValueError(f"Falta el campo {campo}.")
        valor = valor[parte]
    if valor is None or valor == "": raise ValueError(f"Falta el campo {campo}.")
    return valor


def _evento(tipo, referencia, datos, *, canal, cuenta, huella):
    return {"tipo": tipo, "referencia": f"{referencia}:{tipo}", "canal": canal, "cuenta_codigo": cuenta, "datos": {**datos, "origen_fixture_hash": huella}}


def _adaptar_publicacion_ml(payload, cuenta, huella):
    referencia = str(_requerir(payload, "id")); precio = _centavos(_requerir(payload, "price"), "price")
    original = _centavos(payload.get("original_price") or payload["price"], "original_price")
    envio = payload.get("shipping") or {}; cargo = payload.get("sale_fee_amount") or 0
    eventos = [_evento("publicacion", referencia, {"publicacion_id": referencia, "precio_centavos": precio, "estado": payload.get("status"), "tipo_publicacion": payload.get("listing_type_id")}, canal="mercado_libre", cuenta=cuenta, huella=huella)]
    eventos.append(_evento("comision", referencia, {"cargo_venta_observado_centavos": _centavos(cargo, "sale_fee_amount")}, canal="mercado_libre", cuenta=cuenta, huella=huella))
    eventos.append(_evento("envio", referencia, {"envio_gratis": bool(envio.get("free_shipping")), "modo": envio.get("mode")}, canal="mercado_libre", cuenta=cuenta, huella=huella))
    if original > precio:
        descuento = ((Decimal(original - precio) / Decimal(original)) * 100).quantize(Decimal("0.01"))
        eventos.append(_evento("promocion", referencia, {"precio_original_centavos": original, "precio_promocional_centavos": precio, "descuento_pct": str(descuento), "activa": True}, canal="mercado_libre", cuenta=cuenta, huella=huella))
    return eventos


def _adaptar_venta_ml(payload, cuenta, huella):
    referencia = str(_requerir(payload, "id")); items = payload.get("order_items") or []
    if not items: raise ValueError("La venta no contiene order_items.")
    normalizados = []
    for posicion, item in enumerate(items, 1):
        producto = item.get("item") or {}
        normalizados.append({"referencia_item": str(producto.get("id") or posicion), "variante_id": producto.get("variation_id"), "sku": producto.get("seller_sku"), "cantidad": int(item.get("quantity") or 0), "precio_unitario_centavos": _centavos(item.get("unit_price"), "unit_price")})
    return [_evento("venta", referencia, {"venta_id": referencia, "estado": payload.get("status"), "fecha": payload.get("date_created"), "importe_pagado_centavos": _centavos(payload.get("paid_amount") or 0, "paid_amount"), "items": normalizados}, canal="mercado_libre", cuenta=cuenta, huella=huella)]


def _adaptar_pago_mp(payload, cuenta, huella):
    referencia = str(_requerir(payload, "id")); venta = str(payload.get("external_reference") or (payload.get("order") or {}).get("id") or "")
    if not venta: raise ValueError("El pago no contiene referencia de venta.")
    bruto = _centavos(_requerir(payload, "transaction_amount"), "transaction_amount")
    detalle = payload.get("transaction_details") or {}; neto = _centavos(detalle.get("net_received_amount", payload.get("net_received_amount", 0)), "net_received_amount")
    comisiones = sum(_centavos(item.get("amount") or 0, "fee_details.amount") for item in payload.get("fee_details") or [])
    return [_evento("pago", referencia, {"pago_id": referencia, "venta_id": venta, "estado": payload.get("status"), "fecha": payload.get("date_approved"), "bruto_centavos": bruto, "neto_centavos": neto, "comisiones_centavos": comisiones}, canal="mercado_pago", cuenta=cuenta, huella=huella)]


def _adaptar_venta_tn(payload, cuenta, huella):
    referencia = str(_requerir(payload, "id")); productos = payload.get("products") or []
    if not productos: raise ValueError("La venta no contiene products.")
    items = [{"referencia_item": str(item.get("id") or posicion), "variante_id": item.get("variant_id"), "sku": item.get("sku"), "cantidad": int(item.get("quantity") or 0), "precio_unitario_centavos": _centavos(item.get("price"), "products.price")} for posicion, item in enumerate(productos, 1)]
    eventos = [_evento("venta", referencia, {"venta_id": referencia, "estado": payload.get("payment_status"), "fecha": payload.get("created_at"), "importe_total_centavos": _centavos(_requerir(payload, "total"), "total"), "items": items}, canal="tienda_nube", cuenta=cuenta, huella=huella)]
    envio = _centavos(payload.get("shipping_cost_customer") or 0, "shipping_cost_customer")
    if envio: eventos.append(_evento("envio", referencia, {"costo_cliente_centavos": envio}, canal="tienda_nube", cuenta=cuenta, huella=huella))
    descuento = _centavos(payload.get("discount_coupon") or 0, "discount_coupon")
    if descuento > 0: eventos.append(_evento("promocion", referencia, {"descuento_centavos": descuento, "activa": True}, canal="tienda_nube", cuenta=cuenta, huella=huella))
    return eventos


def _adaptar_devolucion(payload, canal, cuenta, huella):
    referencia = str(_requerir(payload, "id")); venta = str(payload.get("order_id") or payload.get("external_reference") or "")
    if not venta: raise ValueError("La devolucion no contiene referencia de venta.")
    return [_evento("devolucion", referencia, {"devolucion_id": referencia, "venta_id": venta, "estado": payload.get("status"), "importe_centavos": _centavos(payload.get("amount") or 0, "amount"), "fecha": payload.get("date_created") or payload.get("created_at")}, canal=canal, cuenta=cuenta, huella=huella)]


def adaptar_fixture(canal, tipo, payload, *, cuenta_codigo):
    canal = str(canal or "").strip().lower(); tipo = str(tipo or "").strip().lower(); cuenta = str(cuenta_codigo or "").strip()
    if canal not in ADAPTADORES or tipo not in ADAPTADORES[canal]: raise ValueError("No existe un adaptador offline para ese canal y tipo.")
    if not cuenta: raise ValueError("La cuenta interna es obligatoria.")
    if not isinstance(payload, dict): raise ValueError("Cada fixture debe ser un objeto JSON.")
    canonico = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")); huella = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    if canal == "mercado_libre" and tipo == "publicacion": eventos = _adaptar_publicacion_ml(payload, cuenta, huella)
    elif canal == "mercado_libre" and tipo == "venta": eventos = _adaptar_venta_ml(payload, cuenta, huella)
    elif canal == "mercado_pago" and tipo == "pago": eventos = _adaptar_pago_mp(payload, cuenta, huella)
    elif canal == "tienda_nube" and tipo == "venta": eventos = _adaptar_venta_tn(payload, cuenta, huella)
    else: eventos = _adaptar_devolucion(payload, canal, cuenta, huella)
    return sorted(eventos, key=lambda evento: (ORDEN_EVENTOS[evento["tipo"]], evento["referencia"]))


def adaptar_documento(canal, tipo, contenido, *, cuenta_codigo):
    if isinstance(contenido, bytes): contenido = contenido.decode("utf-8-sig")
    try: documento = json.loads(contenido)
    except (json.JSONDecodeError, UnicodeDecodeError) as error: raise ValueError("El archivo no contiene JSON UTF-8 valido.") from error
    fixtures = documento if isinstance(documento, list) else [documento]
    eventos = []; errores = []
    for numero, fixture in enumerate(fixtures, 1):
        try: eventos.extend(adaptar_fixture(canal, tipo, fixture, cuenta_codigo=cuenta_codigo))
        except ValueError as error: errores.append({"numero": numero, "error": str(error)})
    return {"eventos": eventos, "errores": errores, "total_fixtures": len(fixtures)}
