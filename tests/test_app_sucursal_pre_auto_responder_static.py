from pathlib import Path


def test_ia_analizar_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "def confirmar_sucursal_via_cargo_ofrecida_sin_responder" in texto

    idx_auto = texto.index("ia_auto_responder_post_analisis(pedido)")
    idx_confirma = texto.rfind(
        "confirmar_sucursal_via_cargo_ofrecida_sin_responder(pedido, _texto_logistica)",
        0,
        idx_auto,
    )

    assert idx_confirma != -1
    assert idx_confirma < idx_auto


def test_confirmacion_sucursal_directa_limpia_pendientes_operativos():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    bloque = texto[idx: idx + 3200]

    assert "pedido.sucursal_nombre = suc.get" in bloque
    assert 'pedido.tipo_entrega = "Sucursal"' in bloque
    assert "pedido.ia_sucursales_ofrecidas = None" in bloque
    assert "pedido.ia_requiere_operador = False" in bloque
    assert "pedido.ia_esperando_respuesta = False" in bloque
    assert "ml_mensajes_pendientes" in bloque


def test_sucursal_directa_redirige_sin_reenviar_confirmacion_repetida():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("confirmar_sucursal_via_cargo_ofrecida_sin_responder(pedido, _texto_logistica)")
    bloque = texto[idx: idx + 900]

    assert "db.session.commit()" in bloque
    assert "return redirect(url_for(" in bloque
    assert "Sucursal confirmada operativamente" in bloque
    assert "No se reenvio confirmacion automatica repetida" in bloque
