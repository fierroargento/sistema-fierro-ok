"""Diagnostico tenant de pedidos Tienda Nube usando fixtures locales."""

import hashlib
import io
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from services.motor_comercial_canal import liquidar_precio


EFECTOS_BLOQUEADOS = {
    "consulta_api": False,
    "persistencia": False,
    "recepcion_externa": False,
    "sincronizacion": False,
    "actualizacion_pedidos": False,
    "acciones_logisticas": False,
}


def _valor(objeto, nombre, default=None):
    if isinstance(objeto, dict):
        return objeto.get(nombre, default)
    return getattr(objeto, nombre, default)


def _texto(objeto, *nombres):
    for nombre in nombres:
        valor = objeto.get(nombre) if isinstance(objeto, dict) else None
        if valor not in (None, ""):
            return str(valor).strip()
    return ""


def _centavos(valor):
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise ValueError("El total del pedido no es valido.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError("El total del pedido no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resolver_cuenta_tenant(vinculo, *, organizacion_id, unidad_negocio_id):
    """Exige un vinculo activo, exacto y con cuenta TN identificable."""
    if vinculo is None:
        raise ValueError("No se selecciono una cuenta Tienda Nube.")
    if _valor(vinculo, "organizacion_id") != organizacion_id:
        raise ValueError("La cuenta no pertenece a la organizacion activa.")
    if _valor(vinculo, "unidad_negocio_id") != unidad_negocio_id:
        raise ValueError("La cuenta no pertenece a la unidad activa.")
    if str(_valor(vinculo, "estado", "")).lower() != "activo":
        raise ValueError("La cuenta Tienda Nube no esta activa.")
    if str(_valor(vinculo, "canal", "")).lower() not in {"tienda_nube", "tiendanube"}:
        raise ValueError("El vinculo seleccionado no es de Tienda Nube.")
    cuenta = _valor(vinculo, "tienda_nube_cuenta")
    cuenta_id = _valor(vinculo, "tienda_nube_cuenta_id") or _valor(cuenta, "id")
    store_id = str(_valor(cuenta, "store_id", "") or "").strip()
    if not cuenta_id or not store_id:
        raise ValueError("La cuenta no tiene store_id interno configurado.")
    return {
        "vinculo_id": int(_valor(vinculo, "id")),
        "cuenta_id": int(cuenta_id),
        "store_id": store_id,
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
    }


def normalizar_pedido(order, contexto):
    if not isinstance(order, dict):
        raise ValueError("Cada pedido debe ser un objeto JSON.")
    order_id = _texto(order, "id", "order_id")
    if not order_id:
        raise ValueError("El pedido no informa id.")
    store_informado = _texto(order, "store_id", "user_id")
    if store_informado and store_informado != contexto["store_id"]:
        raise ValueError("El pedido corresponde a otro store_id.")
    estado = _texto(order, "status").lower()
    pago = _texto(order, "payment_status", "financial_status").lower()
    envio = order.get("shipping_status") or order.get("fulfillment_status") or ""
    envio = str(envio).strip().lower()
    cancelado = estado in {"cancelled", "canceled", "voided"} or bool(order.get("cancelled_at"))
    pagado = pago in {"paid", "approved", "authorized"} or bool(order.get("paid_at"))
    enviado = envio in {"fulfilled", "shipped", "delivered"}
    items = order.get("products") or order.get("items") or []
    if not isinstance(items, list):
        raise ValueError("Los productos del pedido no tienen formato de lista.")
    productos = []
    for numero, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"El producto {numero} no es un objeto JSON.")
        sku = _texto(item, "sku", "variant_sku")
        cantidad = item.get("quantity", 1)
        try:
            cantidad = int(cantidad)
        except (TypeError, ValueError) as error:
            raise ValueError(f"La cantidad del producto {numero} no es valida.") from error
        if cantidad <= 0:
            raise ValueError(f"La cantidad del producto {numero} debe ser positiva.")
        productos.append({
            "sku": sku.upper(),
            "nombre": _texto(item, "name", "product_name") or f"Producto {numero}",
            "cantidad": cantidad,
            "precio_unitario_centavos": _centavos(item.get("price")) if item.get("price") not in (None, "") else None,
            "identificado": bool(sku),
        })
    bloqueos = []
    if cancelado:
        bloqueos.append("pedido_cancelado")
    if not pagado:
        bloqueos.append("pago_no_confirmado")
    if enviado:
        bloqueos.append("pedido_ya_enviado")
    if not productos:
        bloqueos.append("sin_productos")
    if any(not producto["identificado"] for producto in productos):
        bloqueos.append("producto_sin_sku")
    return {
        "identidad": f"{contexto['store_id']}:{order_id}",
        "order_id": order_id,
        "numero": _texto(order, "number", "order_number"),
        "store_id": contexto["store_id"],
        "cuenta_id": contexto["cuenta_id"],
        "organizacion_id": contexto["organizacion_id"],
        "unidad_negocio_id": contexto["unidad_negocio_id"],
        "estado": estado,
        "estado_pago": pago,
        "estado_envio": envio,
        "total_centavos": _centavos(order.get("total", 0)),
        "descuento_centavos": _centavos(order.get("discount", order.get("discount_total", 0))),
        "costo_pago_centavos": _centavos(order.get("payment_cost", order.get("gateway_cost", 0))),
        "costo_envio_centavos": _centavos(order.get("shipping_cost", 0)),
        "productos": productos,
        "telefono_presente": bool(_texto(order, "contact_phone") or _texto(order.get("customer") or {}, "phone") or _texto(order.get("billing_address") or {}, "phone")),
        "cancelado": cancelado,
        "pagado": pagado,
        "enviado": enviado,
        "bloqueos": bloqueos,
        "apto_importacion_simulada": not bloqueos,
        "acciones_externas": 0,
    }


def evaluar_economia_pedido(pedido, controles):
    """Compara ítems observados con el piso interno sin alterar el pedido."""
    indices = {}
    for fila in controles or []:
        sku = str(getattr(getattr(fila.get("costo"), "producto", None), "sku", "") or "").strip().upper()
        if sku:
            indices.setdefault(sku, []).append(fila)
    detalles, bloqueos = [], []
    liquidacion = 0
    piso = 0
    for producto in pedido["productos"]:
        sku = producto["sku"]
        candidatas = indices.get(sku, [])
        if len(candidatas) != 1:
            bloqueos.append(f"{sku or 'SIN-SKU'}:control_interno_{'ausente' if not candidatas else 'ambiguo'}")
            continue
        if producto["precio_unitario_centavos"] is None:
            bloqueos.append(f"{sku}:precio_unitario_no_informado")
            continue
        fila = candidatas[0]
        regla = fila["regla_canal"]
        cantidad = int(producto["cantidad"])
        calculo = liquidar_precio(
            producto["precio_unitario_centavos"],
            comision_pct=regla.comision_pct,
            publicidad_pct=getattr(regla, "publicidad_pct", 0),
            financiacion_pct=getattr(regla, "financiacion_pct", 0),
            devoluciones_pct=getattr(regla, "devoluciones_pct", 0),
            tramos=regla.tramos,
            umbral_envio_centavos=regla.umbral_envio_centavos,
            costo_envio_centavos=regla.costo_envio_default_centavos,
        )
        piso_item = int(fila["minimo"]["piso_liquidacion_centavos"])
        liquidacion += calculo["liquidacion_centavos"] * cantidad
        piso += piso_item * cantidad
        detalles.append({"sku": sku, "cantidad": cantidad, "liquidacion_unitaria_centavos": calculo["liquidacion_centavos"], "piso_unitario_centavos": piso_item})
    liquidacion -= int(pedido.get("costo_pago_centavos", 0) or 0)
    return {
        "estado": "bloqueada" if bloqueos else "debajo_del_piso" if liquidacion < piso else "rentable",
        "liquidacion_estimada_centavos": liquidacion,
        "piso_minimo_centavos": piso,
        "margen_minimo_centavos": liquidacion - piso,
        "bloqueos": bloqueos,
        "detalles": detalles,
        "acciones_externas": 0,
    }


def procesar_fixture_tienda_nube(contenido, vinculo, *, organizacion_id, unidad_negocio_id, controles=None):
    contexto = resolver_cuenta_tenant(
        vinculo,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8-sig")
    try:
        documento = json.loads(contenido) if isinstance(contenido, str) else contenido
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("El archivo no contiene JSON UTF-8 valido.") from error
    filas = documento if isinstance(documento, list) else [documento]
    resultados, errores, identidades = [], [], []
    for numero, order in enumerate(filas, start=1):
        try:
            pedido = normalizar_pedido(order, contexto)
            pedido["control_economico"] = evaluar_economia_pedido(pedido, controles) if controles is not None else None
            if pedido["identidad"] in identidades:
                raise ValueError("El pedido esta duplicado dentro del archivo.")
            identidades.append(pedido["identidad"])
            resultados.append({"fila": numero, **pedido})
        except (ValueError, TypeError) as error:
            errores.append({"fila": numero, "error": str(error)})
    resumen = {
        "filas": len(filas),
        "validas": len(resultados),
        "errores": len(errores),
        "aptas": sum(pedido["apto_importacion_simulada"] for pedido in resultados),
        "bloqueadas": sum(not pedido["apto_importacion_simulada"] for pedido in resultados),
        "sin_telefono": sum(not pedido["telefono_presente"] for pedido in resultados),
        "rentables": sum(pedido.get("control_economico", {}).get("estado") == "rentable" for pedido in resultados if pedido.get("control_economico")),
        "economicamente_bloqueadas": sum(pedido.get("control_economico", {}).get("estado") == "bloqueada" for pedido in resultados if pedido.get("control_economico")),
        "acciones_externas": 0,
    }
    base = {"contexto": contexto, "resultados": resultados, "errores": errores, "resumen": resumen}
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        **base,
        "firma_evidencia": firma,
        "modo": "tienda_nube_offline",
        "efectos": dict(EFECTOS_BLOQUEADOS),
        "escrituras": 0,
        "aplicable": False,
    }


def certificar_escenarios_tienda_nube():
    cuenta = {"id": 8, "store_id": "STORE-DEMO"}
    vinculo = {"id": 4, "organizacion_id": 1, "unidad_negocio_id": 2, "estado": "activo", "canal": "tienda_nube", "tienda_nube_cuenta_id": 8, "tienda_nube_cuenta": cuenta}
    casos = [
        ("pagado", {"id": 1, "total": "1000", "payment_status": "paid", "products": [{"sku": "A", "quantity": 1}]}, True),
        ("impago", {"id": 2, "total": 1000, "payment_status": "pending", "products": [{"sku": "A"}]}, False),
        ("cancelado", {"id": 3, "total": 1000, "payment_status": "paid", "status": "cancelled", "products": [{"sku": "A"}]}, False),
        ("enviado", {"id": 4, "total": 1000, "payment_status": "paid", "shipping_status": "shipped", "products": [{"sku": "A"}]}, False),
        ("sin_sku", {"id": 5, "total": 1000, "payment_status": "paid", "products": [{"name": "Producto"}]}, False),
    ]
    resultados = []
    for codigo, pedido, esperado in casos:
        salida = procesar_fixture_tienda_nube([pedido], vinculo, organizacion_id=1, unidad_negocio_id=2)
        obtenido = salida["resultados"][0]["apto_importacion_simulada"]
        resultados.append({"codigo": codigo, "aprobado": obtenido == esperado, "esperado": esperado, "obtenido": obtenido})
    return {"aprobada": all(caso["aprobado"] for caso in resultados), "casos": resultados, "acciones_externas": 0, "escrituras": 0}


def exportar_diagnostico_tienda_nube(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
