from services.ml_mensajes import (
    ml_obtener_mensajes_pack_para_ia_service,
)


class ApiContextFake:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def get(self, path, params=None):
        self.llamadas.append((path, params))
        respuesta = self.respuestas.pop(0)

        if isinstance(respuesta, Exception):
            raise respuesta

        return respuesta


def test_pack_vacio_no_consulta_api():
    llamadas = []

    resultado = ml_obtener_mensajes_pack_para_ia_service(
        " ",
        api_get_fn=lambda *args, **kwargs: llamadas.append(
            (args, kwargs)
        ),
    )

    assert resultado == []
    assert llamadas == []


def test_usa_contexto_y_respeta_orden_de_intentos_con_seller():
    mensaje = {
        "id": "mensaje-1",
        "from": {"user_type": "buyer"},
        "text": "Hola",
    }
    contexto = ApiContextFake([
        RuntimeError("primer intento"),
        {"messages": []},
        {"messages": [mensaje]},
    ])
    logs = []

    resultado = ml_obtener_mensajes_pack_para_ia_service(
        "123",
        seller_id="456",
        api_context=contexto,
        api_get_fn=lambda *args, **kwargs: (
            (_ for _ in ()).throw(
                AssertionError("No debe usar api_get_fn")
            )
        ),
        logger_fn=logs.append,
    )

    assert resultado == [mensaje]
    assert contexto.llamadas == [
        (
            "/messages/packs/123/sellers/456",
            {"tag": "post_sale", "limit": 50},
        ),
        (
            "/messages/packs/123/sellers/456",
            {"limit": 50},
        ),
        (
            "/messages/packs/123",
            {
                "role": "seller",
                "tag": "post_sale",
                "limit": 50,
            },
        ),
    ]
    assert len(logs) == 1
    assert "primer intento" in logs[0]


def test_sin_contexto_usa_api_get_inyectado():
    llamadas = []
    mensaje = {
        "id": "mensaje-2",
        "sender": {"role": "buyer"},
        "message": "Consulta",
    }

    def api_get(path, params=None):
        llamadas.append((path, params))
        return {"results": [mensaje]}

    resultado = ml_obtener_mensajes_pack_para_ia_service(
        "789",
        api_get_fn=api_get,
    )

    assert resultado == [mensaje]
    assert llamadas == [
        (
            "/messages/packs/789",
            {
                "role": "seller",
                "tag": "post_sale",
                "limit": 50,
            },
        ),
    ]


def test_agota_intentos_y_devuelve_lista_vacia():
    contexto = ApiContextFake([
        {"messages": []},
        {"messages": []},
        {"messages": []},
        {"messages": []},
    ])

    resultado = ml_obtener_mensajes_pack_para_ia_service(
        "123",
        seller_id="456",
        api_context=contexto,
    )

    assert resultado == []
    assert len(contexto.llamadas) == 4
