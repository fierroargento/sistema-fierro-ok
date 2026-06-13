from modules.bot_ml.mensajes_api import (
    ml_obtener_ids_mensajes_pendientes_api,
    ml_resolver_ids_desde_recurso_mensaje_api,
)


def test_ml_resolver_ids_desde_recurso_mensaje_api_extrae_directo_de_resource():
    ids = ml_resolver_ids_desde_recurso_mensaje_api(
        "/packs/20000000001/orders/30000000002",
        lambda path, params=None: {},
    )

    assert ids == {"20000000001", "30000000002"}


def test_ml_resolver_ids_desde_recurso_mensaje_api_devuelve_vacio_sin_resource():
    ids = ml_resolver_ids_desde_recurso_mensaje_api(
        "",
        lambda path, params=None: {},
    )

    assert ids == set()


def test_ml_resolver_ids_desde_recurso_mensaje_api_consulta_detalle_si_no_resuelve_directo():
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))
        return {
            "message_resources": [
                {"id": "20000000001", "name": "packs"},
            ]
        }

    ids = ml_resolver_ids_desde_recurso_mensaje_api(
        "/messages/abc",
        fake_api_get,
    )

    assert ids == {"20000000001"}
    assert llamadas[0] == ("/messages/abc", {})
    assert len(llamadas) == 1


def test_ml_resolver_ids_desde_recurso_mensaje_api_prueba_variantes_si_falla_primera():
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))

        if params == {}:
            return {}

        return {
            "message_resources": [
                {"id": "30000000002", "name": "orders"},
            ]
        }

    ids = ml_resolver_ids_desde_recurso_mensaje_api(
        "/messages/abc",
        fake_api_get,
    )

    assert ids == {"30000000002"}
    assert llamadas[0] == ("/messages/abc", {})
    assert llamadas[1] == ("/messages/abc", {"tag": "post_sale"})


def test_ml_obtener_ids_mensajes_pendientes_api_agrupa_por_id_y_count():
    def fake_api_get(path, params=None):
        if path == "/messages/unread" and params == {"role": "seller"}:
            return {
                "results": [
                    {
                        "count": 2,
                        "message_resources": [
                            {"id": "20000000001", "name": "packs"},
                        ],
                    }
                ]
            }

        if path == "/messages/unread":
            return {
                "results": [
                    {
                        "count": 5,
                        "message_resources": [
                            {"id": "20000000001", "name": "packs"},
                        ],
                    }
                ]
            }

        return {"results": []}

    resultado = ml_obtener_ids_mensajes_pendientes_api(fake_api_get)

    assert resultado == {"20000000001": 5}


def test_ml_obtener_ids_mensajes_pendientes_api_filtra_status_read():
    def fake_api_get(path, params=None):
        return {
            "results": [
                {
                    "status": "read",
                    "count": 1,
                    "message_resources": [
                        {"id": "20000000001", "name": "packs"},
                    ],
                }
            ]
        }

    resultado = ml_obtener_ids_mensajes_pendientes_api(fake_api_get)

    assert resultado == {}


def test_ml_obtener_ids_mensajes_pendientes_api_resuelve_resource_de_mensaje():
    def fake_api_get(path, params=None):
        if path == "/messages/search":
            return {
                "results": [
                    {
                        "status": "unread",
                        "count": 1,
                        "resource": "/messages/abc",
                    }
                ]
            }

        if path == "/messages/abc":
            return {
                "message_resources": [
                    {"id": "30000000002", "name": "orders"},
                ]
            }

        return {"results": []}

    resultado = ml_obtener_ids_mensajes_pendientes_api(fake_api_get)

    assert resultado == {"30000000002": 1}