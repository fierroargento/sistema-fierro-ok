"""
modules.bot_ml.orders_api
-------------------------
Consultas de orders, shipments y billing de Mercado Libre.

APB / SaaS:
- No depende de Flask ni app.py.
- No escribe DB.
- No conoce Pedido.
- Recibe funciones/API client o access_token desde la capa orquestadora.
"""

import json
from datetime import datetime, timedelta
from urllib.request import Request, urlopen


def ml_obtener_usuario_actual_api(api_get_fn):
    return api_get_fn("/users/me")


def ml_obtener_orders_recientes_api(
    cuenta,
    api_get_fn,
    horas=168,
    max_paginas=100,
):
    """
    Trae ordenes operativas recientes de ML con paginacion por ventana de tiempo.
    Evita depender de un limite fijo que puede quedar tapado por ventas Full/omitidas.
    """
    if not cuenta or not getattr(cuenta, "user_id_ml", None):
        raise ValueError("La cuenta de Mercado Libre no tiene user_id asociado.")

    hasta = datetime.utcnow()
    desde = hasta - timedelta(hours=horas)

    limit = 50
    offset = 0
    orders = []

    for _ in range(max_paginas):
        data = api_get_fn(
            "/orders/search",
            params={
                "seller": cuenta.user_id_ml,
                "sort": "date_desc",
                "limit": limit,
                "offset": offset,
                "order.date_created.from": desde.strftime("%Y-%m-%dT%H:%M:%S.000-00:00"),
                "order.date_created.to": hasta.strftime("%Y-%m-%dT%H:%M:%S.999-00:00"),
            },
        )

        resultados = data.get("results") or []
        if not resultados:
            break

        orders.extend(resultados)

        paging = data.get("paging") or {}
        total = int(paging.get("total") or 0)

        offset += limit
        if offset >= total:
            break

    return orders


def ml_obtener_order_api(order_id, api_get_fn):
    order_id = str(order_id or "").strip()
    if not order_id:
        return {}

    try:
        return api_get_fn(f"/orders/{order_id}")

    except Exception as e:
        print("No se pudo consultar order ML:", e)
        return {}


def ml_obtener_shipment_api(shipping_id, api_get_fn):
    if not shipping_id:
        return {}

    try:
        return api_get_fn(f"/shipments/{shipping_id}")

    except Exception as e:
        print("No se pudo consultar shipment ML:", e)
        return {}


def ml_obtener_billing_info_api(order_id, access_token):
    order_id = str(order_id or "").strip()
    access_token = str(access_token or "").strip()

    if not order_id:
        return {}

    if not access_token:
        return {}

    try:
        url = f"https://api.mercadolibre.com/orders/{order_id}/billing_info"

        req = Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Accept", "application/json")
        req.add_header("x-version", "2")

        with urlopen(req) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {}

            return json.loads(raw)

    except Exception as e:
        print("No se pudo consultar billing_info ML:", e)
        return {}