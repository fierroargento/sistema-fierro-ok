from services.ml_claims import ml_obtener_claim_de_order_service


def test_ml_claims_search_usa_resource_order_y_resource_id():
    llamadas = []

    def ml_api_get(endpoint, params=None):
        llamadas.append((endpoint, params))
        return {"data": []}

    claim = ml_obtener_claim_de_order_service(
        "2000017018877668",
        pack_id="2000017018877668",
        ml_api_get=ml_api_get,
    )

    assert claim is None
    assert llamadas == [
        (
            "/post-purchase/v1/claims/search",
            {
                "resource": "order",
                "resource_id": "2000017018877668",
                "limit": 5,
            },
        )
    ]


def test_ml_claims_no_usa_role_seller_ni_resource_id_suelto():
    llamadas = []

    def ml_api_get(endpoint, params=None):
        llamadas.append(params)
        return {"data": []}

    ml_obtener_claim_de_order_service(
        "2000017018877668",
        pack_id="2000017018877668-pack",
        ml_api_get=ml_api_get,
    )

    assert llamadas
    for params in llamadas:
        assert "role" not in params
        assert "resource" in params
        assert "resource_id" in params


def test_ml_claims_devuelve_claim_bloqueante():
    def ml_api_get(endpoint, params=None):
        return {
            "data": [
                {
                    "id": "123",
                    "status": "opened",
                    "resource": "order",
                    "resource_id": "2000017018877668",
                }
            ]
        }

    claim = ml_obtener_claim_de_order_service(
        "2000017018877668",
        ml_api_get=ml_api_get,
    )

    assert claim["id"] == "123"
    assert claim["status"] == "opened"
