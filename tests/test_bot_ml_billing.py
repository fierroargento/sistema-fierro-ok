from modules.bot_ml.billing import (
    buscar_valor_recursivo,
    ml_billing_additional_info_map,
    ml_billing_base,
    ml_buyer_tiene_nombre_real,
    ml_extraer_direccion_billing,
    ml_extraer_documento_billing,
    ml_extraer_nombre_billing,
    ml_extraer_telefono,
    parece_nickname_ml,
)


def test_buscar_valor_recursivo_encuentra_en_dict_anidado():
    data = {
        "buyer": {
            "billing_info": {
                "identification": {
                    "number": "31991373",
                }
            }
        }
    }

    assert buscar_valor_recursivo(data, "number") == "31991373"


def test_ml_billing_base_prefiere_buyer_billing_info():
    billing_info = {
        "buyer": {
            "billing_info": {
                "name": "Juan",
            }
        },
        "billing_info": {
            "name": "Otro",
        },
    }

    assert ml_billing_base(billing_info) == {"name": "Juan"}


def test_ml_billing_additional_info_map_normaliza_lista():
    billing_info = {
        "billing_info": {
            "additional_info": [
                {"type": "DOC_NUMBER", "value": "31991373"},
                {"key": "first_name", "value": "Juan"},
                {"name": "last_name", "value": "Perez"},
            ]
        }
    }

    resultado = ml_billing_additional_info_map(billing_info)

    assert resultado["doc_number"] == "31991373"
    assert resultado["first_name"] == "Juan"
    assert resultado["last_name"] == "Perez"


def test_ml_extraer_documento_billing_desde_identification():
    billing_info = {
        "buyer": {
            "billing_info": {
                "identification": {
                    "number": "31.991.373",
                }
            }
        }
    }

    assert ml_extraer_documento_billing(billing_info) == "31991373"


def test_ml_extraer_documento_billing_ignora_ceros():
    billing_info = {
        "billing_info": {
            "identification": {
                "number": "00000000",
            }
        }
    }

    assert ml_extraer_documento_billing(billing_info) == ""


def test_ml_extraer_nombre_billing_prefiere_business_name():
    billing_info = {
        "billing_info": {
            "business_name": "Fierro SRL",
            "name": "Juan",
            "last_name": "Perez",
        }
    }

    assert ml_extraer_nombre_billing(billing_info) == "Fierro SRL"


def test_ml_extraer_nombre_billing_arma_nombre_apellido():
    billing_info = {
        "billing_info": {
            "name": "Juan",
            "last_name": "Perez",
        }
    }

    assert ml_extraer_nombre_billing(billing_info) == "Juan Perez"


def test_ml_extraer_direccion_billing_arma_direccion_completa():
    billing_info = {
        "billing_info": {
            "address": {
                "street_name": "San Martin",
                "street_number": "123",
                "comment": "Depto A",
                "city_name": "Viedma",
                "state": {
                    "name": "Rio Negro",
                },
                "zip_code": "8500",
            }
        }
    }

    assert ml_extraer_direccion_billing(billing_info) == (
        "San Martin 123, Depto A, Viedma, Rio Negro, 8500"
    )


def test_ml_extraer_telefono_desde_buyer_phone():
    order = {
        "buyer": {
            "phone": {
                "area_code": "2346",
                "number": "513896",
            }
        }
    }

    assert ml_extraer_telefono(order, {}) == "5492346513896"


def test_ml_extraer_telefono_desde_shipment_receiver_address():
    order = {
        "buyer": {
            "phone": {}
        }
    }
    shipment = {
        "receiver_address": {
            "receiver_phone": "2346513896",
        }
    }

    assert ml_extraer_telefono(order, shipment) == "5492346513896"


def test_ml_buyer_tiene_nombre_real():
    assert ml_buyer_tiene_nombre_real({
        "buyer": {
            "first_name": "Juan",
            "last_name": "Perez",
        }
    }) is True

    assert ml_buyer_tiene_nombre_real({
        "buyer": {
            "first_name": "Juan",
            "last_name": "",
        }
    }) is False


def test_parece_nickname_ml_detecta_nickname_y_genericos():
    assert parece_nickname_ml("", "") is True
    assert parece_nickname_ml("Cliente Mercado Libre", "") is True
    assert parece_nickname_ml("JUAN123", "") is True
    assert parece_nickname_ml("NICKNAME", "NICKNAME") is True
    assert parece_nickname_ml("Juan Perez", "juanperez") is False