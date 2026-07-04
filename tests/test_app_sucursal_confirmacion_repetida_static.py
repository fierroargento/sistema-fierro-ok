from pathlib import Path


def test_app_detecta_sucursal_via_si_hay_opciones_ofrecidas_sin_excluir_pp6040():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("_puede_detectar_sucursal = (")
    bloque = texto[idx: idx + 350]

    assert "_correo_sucursales_ya_ofrecidas" in bloque
    assert "or _via_sucursales_ya_ofrecidas" in bloque
    assert "not pedido_es_plegable_pp6040(pedido)" not in bloque


def test_app_mensaje_repetido_no_corta_confirmacion_sucursal_operativa():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("[CANAL-MANAGER] ML bloqueado pedido")
    bloque = texto[idx: idx + 700]

    assert "mensaje_automatico_repetido" in bloque
    assert '"repetido" in motivo_normalizado' in bloque
    assert "if not mensaje_automatico_repetido:" in bloque
    assert "return False, motivo" in bloque

    idx_repetido = bloque.index("mensaje_automatico_repetido")
    idx_return = bloque.index("return False, motivo")
    assert idx_repetido < idx_return
