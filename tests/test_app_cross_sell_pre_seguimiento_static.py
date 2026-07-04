from pathlib import Path


def test_app_guarda_seguimiento_pasa_por_cross_sell_antes_de_tracking():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "def intentar_cross_sell_previo_seguimiento_wa" in texto
    assert "intentar_wa_cross_sell_antes_de_seguimiento" in texto
    assert 'motivo="seguimiento_cargado_pre_despacho"' in texto

    idx = texto.index('Error enviando seguimiento al guardar tracking:')
    bloque = texto[max(0, idx - 700): idx + 200]
    assert "intentar_cross_sell_previo_seguimiento_wa(pedido)" in bloque
    assert "wa_enviar_numero_seguimiento(pedido)" in bloque
    assert bloque.index("intentar_cross_sell_previo_seguimiento_wa") < bloque.index("wa_enviar_numero_seguimiento")


def test_app_edicion_general_pasa_por_cross_sell_antes_de_tracking():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index('Error enviando seguimiento al guardar tracking desde edici')
    bloque = texto[max(0, idx - 700): idx + 240]
    assert "intentar_cross_sell_previo_seguimiento_wa(pedido)" in bloque
    assert "wa_enviar_numero_seguimiento(pedido)" in bloque
    assert bloque.index("intentar_cross_sell_previo_seguimiento_wa") < bloque.index("wa_enviar_numero_seguimiento")
