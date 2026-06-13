from modules.bot_ml.mensajes import (
    ml_bloque_mensajes_comprador_pendientes,
    ml_extraer_ids_mensaje_ml,
    ml_extraer_lista_mensajes_ml,
    ml_fecha_mensaje_valor,
    ml_mensaje_es_del_comprador,
    ml_mensaje_es_del_vendedor,
    ml_mensaje_esta_pendiente,
    ml_texto_mensaje_ml,
    ml_ultimo_mensaje_comprador,
)


def test_ml_extraer_ids_mensaje_ml_detecta_pack_y_order_en_resource():
    data = {
        "resource": "/packs/20000000001/orders/30000000002",
    }

    assert ml_extraer_ids_mensaje_ml(data) == {
        "20000000001",
        "30000000002",
    }


def test_ml_extraer_ids_mensaje_ml_detecta_message_resources():
    data = {
        "message_resources": [
            {"id": "20000000001", "name": "packs"},
            {"id": "30000000002", "name": "orders"},
        ]
    }

    assert ml_extraer_ids_mensaje_ml(data) == {
        "20000000001",
        "30000000002",
    }


def test_ml_extraer_lista_mensajes_ml_extrae_y_deduplica():
    data = {
        "results": [
            {"id": "1", "text": "Hola"},
            {"id": "1", "text": "Hola duplicado"},
            {"message_id": "2", "message": "Segundo"},
        ]
    }

    resultado = ml_extraer_lista_mensajes_ml(data)

    assert len(resultado) == 2
    assert resultado[0]["id"] == "1"
    assert resultado[1]["message_id"] == "2"


def test_ml_mensaje_es_del_comprador_por_user_type():
    mensaje = {
        "from": {
            "user_type": "buyer",
        }
    }

    assert ml_mensaje_es_del_comprador(mensaje, seller_id="seller-1") is True


def test_ml_mensaje_es_del_comprador_por_sender_distinto_al_seller():
    mensaje = {
        "from": {
            "id": "buyer-1",
        }
    }

    assert ml_mensaje_es_del_comprador(mensaje, seller_id="seller-1") is True


def test_ml_mensaje_es_del_vendedor_por_user_type():
    mensaje = {
        "from": {
            "user_type": "seller",
        }
    }

    assert ml_mensaje_es_del_vendedor(mensaje, seller_id="seller-1") is True


def test_ml_mensaje_es_del_vendedor_por_id_seller():
    mensaje = {
        "from": {
            "id": "seller-1",
        }
    }

    assert ml_mensaje_es_del_vendedor(mensaje, seller_id="seller-1") is True


def test_ml_mensaje_esta_pendiente_por_status():
    assert ml_mensaje_esta_pendiente({"status": "unread"}) is True
    assert ml_mensaje_esta_pendiente({"status": "read"}) is False


def test_ml_mensaje_esta_pendiente_por_read_false():
    assert ml_mensaje_esta_pendiente({"read": False}) is True


def test_ml_fecha_mensaje_valor_extrae_fecha_simple_y_anidada():
    assert ml_fecha_mensaje_valor({"date_created": "2026-01-01"}) == "2026-01-01"
    assert ml_fecha_mensaje_valor({"message_date": {"created": "2026-01-02"}}) == "2026-01-02"


def test_ml_texto_mensaje_ml_extrae_texto_simple_y_anidado():
    assert ml_texto_mensaje_ml({"text": " Hola "}) == "Hola"
    assert ml_texto_mensaje_ml({"content": {"plain": "Texto anidado"}}) == "Texto anidado"


def test_ml_texto_mensaje_ml_detecta_adjunto():
    assert ml_texto_mensaje_ml({"attachments": [{"id": "adj-1"}]}) == (
        "[El comprador envio un adjunto o imagen]"
    )


def test_ml_ultimo_mensaje_comprador_devuelve_el_mas_reciente():
    mensajes = [
        {
            "from": {"user_type": "buyer"},
            "text": "Primero",
            "date_created": "2026-01-01T10:00:00",
        },
        {
            "from": {"user_type": "buyer"},
            "text": "Segundo",
            "date_created": "2026-01-01T11:00:00",
        },
    ]

    resultado = ml_ultimo_mensaje_comprador(mensajes, seller_id="seller-1")

    assert resultado["text"] == "Segundo"


def test_ml_bloque_mensajes_comprador_pendientes_toma_posteriores_al_vendedor():
    mensajes = [
        {
            "from": {"user_type": "buyer"},
            "text": "Dato viejo",
            "date_created": "2026-01-01T09:00:00",
        },
        {
            "from": {"user_type": "seller"},
            "text": "Mensaje vendedor",
            "date_created": "2026-01-01T10:00:00",
        },
        {
            "from": {"user_type": "buyer"},
            "text": "Nombre Juan",
            "date_created": "2026-01-01T11:00:00",
        },
        {
            "from": {"user_type": "buyer"},
            "text": "DNI 31991373",
            "date_created": "2026-01-01T12:00:00",
        },
    ]

    resultado = ml_bloque_mensajes_comprador_pendientes(
        mensajes,
        seller_id="seller-1",
    )

    assert resultado == "Nombre Juan\n\nDNI 31991373"