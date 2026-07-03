from pathlib import Path


def app_texto():
    return Path("app.py").read_text(encoding="utf-8")


def bloque_funcion(texto, nombre_funcion):
    inicio = texto.index(f"def {nombre_funcion}")
    siguiente = texto.find("\ndef ", inicio + 1)

    if siguiente == -1:
        return texto[inicio:]

    return texto[inicio:siguiente]


def test_ml_obtener_mensajes_para_ia_acepta_api_context():
    texto = app_texto()
    bloque = bloque_funcion(texto, "ml_obtener_mensajes_pack_para_ia")

    assert 'def ml_obtener_mensajes_pack_para_ia(pack_id, seller_id="", api_context=None):' in bloque
    assert "if api_context is not None:" in bloque
    assert "data = api_context.get(path, params=params)" in bloque


def test_ml_sync_mensajes_pack_usa_contexto_por_pedido():
    texto = app_texto()
    bloque = bloque_funcion(texto, "ml_sync_mensajes_pack")

    assert "MercadoLibreCuenta.query.first()" not in bloque
    assert "cuenta_por_pedido_o_backfill_unica(" in bloque
    assert "cuenta_default(" in bloque
    assert "ml_api_contexto(" in bloque
    assert "api_context.get(path, params=params)" in bloque


def test_ml_mensaje_thread_habilitado_usa_contexto_por_pedido():
    texto = app_texto()
    bloque = bloque_funcion(texto, "ml_mensaje_thread_habilitado")

    assert "MercadoLibreCuenta.query.first()" not in bloque
    assert "cuenta_por_pedido_o_backfill_unica(" in bloque
    assert "ml_api_contexto(" in bloque
    assert "api_context.get(" in bloque


def test_ml_enviar_mensaje_acordas_usa_contexto_por_pedido():
    texto = app_texto()
    bloque = bloque_funcion(texto, "ml_enviar_mensaje_acordas")

    assert "MercadoLibreCuenta.query.first()" not in bloque
    assert "cuenta_por_pedido_o_backfill_unica(" in bloque
    assert "ml_api_contexto(" in bloque
    assert "resultado_ml = api_context.post_json(path, payload)" in bloque


def test_ia_manual_usa_contexto_por_pedido():
    texto = app_texto()
    bloque = bloque_funcion(texto, "ia_analizar_respuesta_pedido")

    assert "MercadoLibreCuenta.query.first()" not in bloque
    assert "cuenta_por_pedido_o_backfill_unica(" in bloque
    assert "ml_api_contexto(" in bloque
    assert "api_context=api_context" in bloque
    assert "No se pudo resolver cuenta de Mercado Libre del pedido" in bloque
