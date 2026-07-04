from pathlib import Path


def test_helper_recupera_transicion_ml_wa_con_sucursal_ya_confirmada():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "def iniciar_transicion_ml_wa_si_sucursal_ya_confirmada" in texto

    idx = texto.index("def iniciar_transicion_ml_wa_si_sucursal_ya_confirmada")
    bloque = texto[idx: idx + 2600]

    assert "sucursal_nombre" in bloque
    assert "msg_transicion_wa" in bloque
    assert "ml_enviar_mensaje_acordas(" in bloque
    assert "intentar_wa_cross_sell_tras_sucursal_ml(" in bloque
    assert "return True" in bloque


def test_analisis_ia_llama_recuperacion_tras_guardar_resultado():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_guardar = texto.index("ia_guardar_resultado_recolector(pedido, texto, resultado)")
    idx_recupera = texto.index("iniciar_transicion_ml_wa_si_sucursal_ya_confirmada(", idx_guardar)
    idx_auto = texto.index("ia_auto_responder_post_analisis(pedido)", idx_guardar)

    assert idx_guardar < idx_recupera < idx_auto
    assert 'motivo="sucursal_ya_confirmada_reanalisis_ml"' in texto[idx_recupera:idx_auto]
