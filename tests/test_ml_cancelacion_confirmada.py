from services.ml_cancelacion_confirmada import (
    ml_order_tiene_cancelacion_o_reembolso,
    ml_claim_tiene_reembolso,
    marcar_evidencia_ml_cancelacion_en_pedido,
    MARCA_EVIDENCIA_ML_CANCELACION,
)


class PedidoDummy:
    def __init__(self):
        self.observaciones = ""


def test_ml_order_cancelled_confirma_cancelacion():
    assert ml_order_tiene_cancelacion_o_reembolso({"status": "cancelled"})


def test_ml_order_payment_refunded_confirma_reembolso():
    order = {
        "status": "paid",
        "payments": [
            {
                "status": "refunded",
                "status_detail": "",
            }
        ],
    }

    assert ml_order_tiene_cancelacion_o_reembolso(order)


def test_ml_order_transaction_amount_refunded_confirma_reembolso():
    order = {
        "status": "paid",
        "payments": [
            {
                "status": "approved",
                "transaction_amount_refunded": 12000,
            }
        ],
    }

    assert ml_order_tiene_cancelacion_o_reembolso(order)


def test_ml_order_pagada_sin_reembolso_no_confirma():
    order = {
        "status": "paid",
        "payments": [
            {
                "status": "approved",
                "status_detail": "accredited",
            }
        ],
    }

    assert not ml_order_tiene_cancelacion_o_reembolso(order)


def test_ml_claim_closed_con_refund_confirma_reembolso():
    claim = {
        "status": "closed",
        "resolution": {
            "reason": "refund_buyer",
        },
    }

    assert ml_claim_tiene_reembolso(claim)


def test_marcar_evidencia_ml_cancelacion_en_pedido_agrega_observacion():
    pedido = PedidoDummy()

    assert marcar_evidencia_ml_cancelacion_en_pedido(pedido, "payment refunded")
    assert MARCA_EVIDENCIA_ML_CANCELACION in pedido.observaciones


def test_extrae_order_desde_search_por_pack_id():
    from services.ml_cancelacion_confirmada import ml_extraer_order_de_search_por_pack

    data = {
        "results": [
            {"id": 111, "pack_id": 999},
            {"id": 222, "pack_id": 123},
        ]
    }

    assert ml_extraer_order_de_search_por_pack(data, "123")["id"] == 222


def test_extrae_order_unico_desde_search_aunque_no_traiga_pack_id():
    from services.ml_cancelacion_confirmada import ml_extraer_order_de_search_por_pack

    data = {
        "results": [
            {"id": 222, "status": "paid"},
        ]
    }

    assert ml_extraer_order_de_search_por_pack(data, "123")["id"] == 222
