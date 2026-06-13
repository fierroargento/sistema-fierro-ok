"""
modules.bot_ml.mensajes_api
---------------------------
Consultas API de mensajes Mercado Libre.

APB / SaaS:
- No escribe DB.
- No conoce Pedido.
- No depende de Flask ni app.py.
- Recibe api_get_fn desde la capa orquestadora.
"""

from modules.bot_ml.mensajes import ml_extraer_ids_mensaje_ml


def ml_resolver_ids_desde_recurso_mensaje_api(resource, api_get_fn):
    """Intenta resolver pack/order IDs desde el recurso de mensaje que manda ML."""
    resource = str(resource or "").strip()

    if not resource:
        return set()

    ids = ml_extraer_ids_mensaje_ml({"resource": resource})
    if ids:
        return ids

    if not resource.startswith("/"):
        return set()

    intentos = [(resource, {})]

    # En algunas cuentas, el detalle del mensaje postventa necesita tag=post_sale.
    if "/messages" in resource:
        intentos.append((resource, {"tag": "post_sale"}))
        intentos.append((resource, {"role": "seller", "tag": "post_sale"}))

    for path, params in intentos:
        try:
            detalle = api_get_fn(path, params=params)
            ids = ml_extraer_ids_mensaje_ml(detalle)

            print(
                "[ML-MENSAJE-DETALLE] resource=",
                path,
                params,
                "ids=",
                sorted(ids),
            )

            if ids:
                return ids

        except Exception as e:
            print("[ML-MENSAJE-DETALLE] No se pudo resolver", path, params, e)

    return set()


def ml_obtener_ids_mensajes_pendientes_api(api_get_fn):
    """
    Obtiene IDs con mensajes pendientes sin abrir el chat del pedido.
    Usa varios endpoints/formas porque ML cambia la estructura segun flujo/cuenta.
    """
    pendientes_por_id = {}

    endpoints = [
        ("/messages/unread", {"role": "seller"}),
        ("/messages/unread", {"role": "seller", "tag": "post_sale"}),
        ("/messages/search", {"role": "seller", "limit": 50}),
    ]

    for path, params in endpoints:
        try:
            data = api_get_fn(path, params=params)
            print(f"[ML-MENSAJES] OK {path} {params}")

        except Exception as e:
            print(f"[ML-MENSAJES] No se pudo consultar {path} {params}: {e}")
            continue

        resultados = (data or {}).get("results") if isinstance(data, dict) else data

        if isinstance(resultados, dict):
            resultados = resultados.get("results") or resultados.get("items") or []

        if not isinstance(resultados, list):
            resultados = []

        for item in resultados:
            # En search puede venir status/read distinto. Si hay status y NO es unread, salteamos.
            estado_msg = str(
                (item or {}).get("status")
                or (item or {}).get("message_status")
                or ""
            ).lower()

            if estado_msg and estado_msg not in {"unread", "new", "pending"}:
                continue

            try:
                count = int((item or {}).get("count") or (item or {}).get("unread") or 1)
            except Exception:
                count = 1

            if count <= 0:
                continue

            ids_item = ml_extraer_ids_mensaje_ml(item)

            # Si ML solo devuelve resource del mensaje, resolvemos el detalle puntual.
            if not ids_item:
                resource = (item or {}).get("resource") or (item or {}).get("message_id") or ""

                if resource and str(resource).startswith("/messages"):
                    ids_item = ml_resolver_ids_desde_recurso_mensaje_api(
                        resource,
                        api_get_fn,
                    )

            for id_ref in ids_item:
                pendientes_por_id[id_ref] = max(
                    int(pendientes_por_id.get(id_ref) or 0),
                    count,
                )

    return pendientes_por_id