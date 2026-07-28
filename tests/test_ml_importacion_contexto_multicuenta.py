from types import SimpleNamespace

from services.ml_api_context import MLApiContext


def crear_contexto(cuenta, llamadas):
    def get_fn(token, path, params=None):
        llamadas.append(
            ("get", token, path, params)
        )
        return {"token": token}

    def get_binario_fn(
        token,
        path,
        params=None,
        accept="application/pdf",
    ):
        llamadas.append(
            (
                "binario",
                token,
                path,
                params,
                accept,
            )
        )
        return b"%PDF-prueba", "application/pdf"

    return MLApiContext(
        cuenta,
        token_vencido_fn=lambda _cuenta: False,
        get_fn=get_fn,
        get_binario_fn=get_binario_fn,
    )


def test_dos_contextos_importacion_no_comparten_token():
    llamadas = []

    contexto_1 = crear_contexto(
        SimpleNamespace(
            id=1,
            user_id_ml="111",
            access_token="token-111",
        ),
        llamadas,
    )
    contexto_2 = crear_contexto(
        SimpleNamespace(
            id=2,
            user_id_ml="222",
            access_token="token-222",
        ),
        llamadas,
    )

    contexto_1.get("/shipments/shipment-111")
    contexto_2.get("/shipments/shipment-222")
    contexto_1.get_binario(
        "/shipment_labels",
        params={"shipment_ids": "shipment-111"},
    )
    contexto_2.get_binario(
        "/shipment_labels",
        params={"shipment_ids": "shipment-222"},
    )

    assert contexto_1.asegurar_token() == "token-111"
    assert contexto_2.asegurar_token() == "token-222"
    assert llamadas == [
        (
            "get",
            "token-111",
            "/shipments/shipment-111",
            None,
        ),
        (
            "get",
            "token-222",
            "/shipments/shipment-222",
            None,
        ),
        (
            "binario",
            "token-111",
            "/shipment_labels",
            {"shipment_ids": "shipment-111"},
            "application/pdf",
        ),
        (
            "binario",
            "token-222",
            "/shipment_labels",
            {"shipment_ids": "shipment-222"},
            "application/pdf",
        ),
    ]
