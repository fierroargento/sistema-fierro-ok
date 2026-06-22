import json
from datetime import datetime, UTC

from domain.estados import Estado

CLAIM_ESTADOS_BLOQUEANTES = {
    "opened",
    "under_review",
    "mediating",
    "claim_opened",
}

CLAIM_ESTADOS_REEMBOLSO = {
    "closed",
    "resolved",
    "refunded",
    "buyer_won",
}

def ml_obtener_claim_de_order_service(
    order_id,
    pack_id=None,
    ml_api_get=None,
):
    """
    Busca un reclamo activo para una order/pack en Mercado Libre.
    Devuelve el claim dict o None.
    """

    order_id = str(order_id or "").strip()
    pack_id = str(pack_id or "").strip()

    consultas = []

    # APB:
    # claims/search requiere filtros válidos.
    # Mercado Libre/Mercado Pago acepta resource + resource_id.
    # Evitamos resource_id suelto y role=seller porque generan 400.
    if order_id:
        consultas.append({
            "resource": "order",
            "resource_id": order_id,
            "limit": 5,
        })

    ids_pack_posibles = []

    if pack_id:
        ids_pack_posibles.append(pack_id)

    # En algunos flujos de Mercado Envíos el valor guardado como id_venta
    # funciona en ML como pack/venta agrupada, pero no como /orders/{id}.
    # Por eso lo probamos también como resource=pack.
    if order_id and order_id not in ids_pack_posibles:
        ids_pack_posibles.append(order_id)

    for pack_id_posible in ids_pack_posibles:
        consultas.append({
            "resource": "pack",
            "resource_id": pack_id_posible,
            "limit": 5,
        })

    for params in consultas:
        try:
            data = ml_api_get(
                "/post-purchase/v1/claims/search",
                params=params,
            )

            claims = []

            if isinstance(data, dict):
                claims = (
                    data.get("data")
                    or data.get("results")
                    or data.get("claims")
                    or []
                )

            elif isinstance(data, list):
                claims = data

            if not isinstance(claims, list):
                claims = []

            for claim in claims:
                status = str(
                    (claim or {}).get("status")
                    or ""
                ).lower().strip()

                resolution = str(
                    (claim or {}).get("resolution")
                    or {}
                )

                # Bloqueante:
                # reclamo activo O cerrado con reembolso al comprador.
                if status in CLAIM_ESTADOS_BLOQUEANTES:
                    return claim

                if (
                    status in CLAIM_ESTADOS_REEMBOLSO
                    and "buyer" in resolution.lower()
                ):
                    return claim

        except Exception as e:
            print(
                f"[ML-CLAIMS] Error buscando claim params={params}: {e}"
            )

    return None

def ml_pedido_tiene_claim_service(pedido):
    return bool(
        pedido
        and getattr(pedido, "ml_claim_abierto", False)
    )


def ml_marcar_claim_en_pedido_service(
    pedido,
    claim,
):
    """
    Guarda o limpia datos del reclamo ML en el pedido.
    """

    if not pedido:
        return

    if claim:
        pedido.ml_claim_id = str(
            claim.get("id")
            or claim.get("claim_id")
            or ""
        ).strip()

        pedido.ml_claim_abierto = True

        pedido.ml_claim_status = str(
            claim.get("status")
            or ""
        ).lower().strip()

        pedido.ml_claim_reason = str(
            claim.get("reason_id")
            or claim.get("type")
            or claim.get("stage")
            or ""
        ).strip()

        # APB:
        # Reclamo cerrado con devolución/reembolso
        # implica fin operativo del pedido.

        status = pedido.ml_claim_status

        resolution_raw = claim.get("resolution") or ""

        if isinstance(resolution_raw, dict):
            resolution = json.dumps(
                resolution_raw,
                ensure_ascii=False,
            ).lower()

        else:
            resolution = str(
                resolution_raw
            ).lower()

        palabras_reembolso = [
            "refund",
            "refunded",
            "buyer",
            "return",
            "money_back",
            "devol",
        ]

        hay_reembolso = any(
            palabra in resolution
            for palabra in palabras_reembolso
        )

        if (
            status in [
                "closed",
                "resolved",
            ]
            and hay_reembolso
        ):

            if pedido.estado != Estado.FINALIZADO:

                pedido.estado = Estado.FINALIZADO

                observacion_actual = (
                    pedido.observaciones or ""
                ).strip()

                marca = (
                    "ML informó reclamo cerrado "
                    "con reembolso al comprador."
                )

                if marca not in observacion_actual:
                    pedido.observaciones = (
                        f"{observacion_actual}\n{marca}"
                    ).strip()

                print(
                    f"[ML-CLAIMS] Pedido #{pedido.id} "
                    f"finalizado automáticamente "
                    f"por reclamo con reembolso"
                )

    else:
        pedido.ml_claim_abierto = False
        pedido.ml_claim_status = ""
        pedido.ml_claim_reason = ""

    pedido.ultima_sync_claim_ml = datetime.now(UTC)

def ml_sync_claims_pedidos_operativos_service(
    Pedido,
    db,
    cuenta_ml_actual,
    ml_obtener_claim_de_order,
    ml_marcar_claim_en_pedido,
    estados_operativos,
):
    """
    Consulta claims para pedidos ML operativos.
    Respaldo para cuando el webhook no trae/impacta el evento.
    """

    cuenta = cuenta_ml_actual()

    if not cuenta:
        return 0

    pedidos = Pedido.query.filter(
        Pedido.canal == "Mercado Libre",
        Pedido.estado.in_(estados_operativos),
    ).all()

    marcados = 0

    for pedido in pedidos:
        order_id = str(
            getattr(pedido, "id_venta", "") or ""
        ).strip()

        pack_id = str(
            getattr(pedido, "ml_pack_id", "") or ""
        ).strip()

        if not order_id and not pack_id:
            continue

        claim = ml_obtener_claim_de_order(
            order_id,
            pack_id,
        )

        ml_marcar_claim_en_pedido(
            pedido,
            claim,
        )

        if claim:
            marcados += 1

    try:
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ML-CLAIMS-SYNC] Error commit: {e}")

    return marcados    