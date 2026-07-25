"""
Consulta canónica de mensajes de Mercado Libre.

No depende de Flask, app.py ni de una cuenta global.
La llamada HTTP se recibe explícitamente o mediante MLApiContext.
"""

from modules.bot_ml.mensajes import (
    ml_extraer_lista_mensajes_ml,
)


def ml_obtener_mensajes_pack_para_ia_service(
    pack_id,
    seller_id="",
    api_context=None,
    api_get_fn=None,
    logger_fn=print,
):
    """Obtiene mensajes de un thread ML sin marcarlos como leídos."""
    pack_id = str(pack_id or "").strip()

    if not pack_id:
        return []

    seller_id = str(seller_id or "").strip()
    intentos = []

    if seller_id:
        path_seller = (
            f"/messages/packs/{pack_id}/sellers/{seller_id}"
        )
        intentos.append((
            path_seller,
            {"tag": "post_sale", "limit": 50},
        ))
        intentos.append((
            path_seller,
            {"limit": 50},
        ))

    path_pack = f"/messages/packs/{pack_id}"
    intentos.append((
        path_pack,
        {
            "role": "seller",
            "tag": "post_sale",
            "limit": 50,
        },
    ))
    intentos.append((
        path_pack,
        {
            "role": "seller",
            "limit": 50,
        },
    ))

    for path, params in intentos:
        try:
            if api_context is not None:
                data = api_context.get(
                    path,
                    params=params,
                )
            elif api_get_fn is not None:
                data = api_get_fn(
                    path,
                    params=params,
                )
            else:
                raise ValueError(
                    "Se requiere api_context o api_get_fn."
                )

            mensajes = ml_extraer_lista_mensajes_ml(data)

            if mensajes:
                return mensajes

        except Exception as e:
            if logger_fn:
                logger_fn(
                    "[IA-RECOLECTOR] Fallo leyendo mensajes "
                    f"{path} {params}: {e}"
                )

    return []
