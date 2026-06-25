from services.wa_general_bot import (
    ACCION_AGRADECIMIENTO,
    ACCION_ESCALAR_OPERADOR,
    ACCION_MENU_CONTACTO_NUEVO,
    clasificar_sin_pedido_activo_wa_general,
    es_agradecimiento_wa_general,
    respuesta_agradecimiento_wa_general,
    respuesta_menu_contacto_nuevo_wa_general,
)


def test_detecta_agradecimiento_y_recomendacion():
    texto = "GRACIAS A USTEDES LA VERDAD ME ENCANTA LA PARRILLA LOS VOY A RECOMENDAR"

    assert es_agradecimiento_wa_general(texto) is True
    assert clasificar_sin_pedido_activo_wa_general(
        texto,
        tiene_historial_pedidos=True,
    ) == ACCION_AGRADECIMIENTO


def test_no_toma_como_agradecimiento_si_hay_problema():
    texto = "gracias pero me llego roto"

    assert es_agradecimiento_wa_general(texto) is False
    assert clasificar_sin_pedido_activo_wa_general(
        texto,
        tiene_historial_pedidos=True,
    ) == ACCION_ESCALAR_OPERADOR


def test_cliente_con_historial_sin_pedido_activo_escala():
    assert clasificar_sin_pedido_activo_wa_general(
        "Necesito hacer una consulta",
        tiene_historial_pedidos=True,
    ) == ACCION_ESCALAR_OPERADOR


def test_contacto_nuevo_recibe_menu():
    assert clasificar_sin_pedido_activo_wa_general(
        "Hola",
        tiene_historial_pedidos=False,
        tiene_historial_whatsapp=False,
    ) == ACCION_MENU_CONTACTO_NUEVO


def test_opcion_de_menu_no_repite_menu():
    assert clasificar_sin_pedido_activo_wa_general(
        "1",
        tiene_historial_pedidos=False,
        tiene_historial_whatsapp=False,
    ) == ACCION_ESCALAR_OPERADOR


def test_respuestas_tienen_texto_humano_con_unicode():
    agradecimiento = respuesta_agradecimiento_wa_general()
    menu = respuesta_menu_contacto_nuevo_wa_general()

    assert "Qu\u00e9 alegr\u00eda" in agradecimiento
    assert "\U0001f60a" in agradecimiento
    assert "respond\u00e9 con una opci\u00f3n" in menu
    assert "\U0001f44b" in menu
