from pathlib import Path


def test_flujo_comun_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "def confirmar_sucursal_via_cargo_ofrecida_sin_responder" in texto

    idx_guardar = texto.index("ia_guardar_resultado_recolector(pedido, texto, resultado)")
    idx_confirma = texto.index(
        "confirmar_sucursal_via_cargo_ofrecida_sin_responder(pedido, texto)",
        idx_guardar,
    )
    idx_auto = texto.index("ia_auto_responder_post_analisis(pedido)", idx_guardar)

    assert idx_guardar < idx_confirma < idx_auto


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


def test_flujo_comun_retorna_resultado_sucursal_confirmada_sin_auto_responder():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("confirmar_sucursal_via_cargo_ofrecida_sin_responder(pedido, texto)")
    bloque = texto[idx: idx + 900]

    assert "actualizar_estado_automatico(pedido)" in bloque
    assert "db.session.commit()" in bloque
    assert '"estado": "sucursal_confirmada"' in bloque
    assert '"sucursal_confirmada": True' in bloque
    assert "return {" in bloque
