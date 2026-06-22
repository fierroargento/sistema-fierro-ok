from services.ml_claims import ml_obtener_claim_de_order_service


def test_ml_obtener_claim_busca_por_pack_id_si_order_no_tiene_claim():
    llamadas = []

    def fake_ml_api_get(path, params=None):
        llamadas.append(params)

        if params.get("resource") == "pack":
            return {
                "data": [
                    {
                        "id": 123,
                        "status": "closed",
                        "resolution": {
                            "reason": "refund_buyer",
                        },
                    }
                ]
            }

        return {"data": []}

    claim = ml_obtener_claim_de_order_service(
        "2000013604462501",
        pack_id="2000013604462501",
        ml_api_get=fake_ml_api_get,
    )

    assert claim["id"] == 123
    assert any(params.get("resource") == "pack" for params in llamadas)


def test_ml_obtener_claim_prueba_order_id_como_pack_si_no_hay_pack_id():
    llamadas = []

    def fake_ml_api_get(path, params=None):
        llamadas.append(params)

        if params.get("resource") == "pack":
            return {
                "results": [
                    {
                        "id": 456,
                        "status": "closed",
                        "resolution": "refund_buyer",
                    }
                ]
            }

        return {"results": []}

    claim = ml_obtener_claim_de_order_service(
        "2000013604462501",
        pack_id="",
        ml_api_get=fake_ml_api_get,
    )

    assert claim["id"] == 456
    assert any(params.get("resource") == "pack" for params in llamadas)
