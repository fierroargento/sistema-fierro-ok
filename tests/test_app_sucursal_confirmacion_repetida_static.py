from pathlib import Path


def test_app_detector_distingue_correo_de_via_para_pp6040():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("_puede_detectar_sucursal = (")
    bloque = texto[idx: idx + 450]

    assert "_correo_sucursales_ya_ofrecidas" in bloque
    assert "_via_sucursales_ya_ofrecidas" in bloque
    assert "not pedido_es_plegable_pp6040(pedido)" in bloque

    idx_correo = bloque.index(
        "_correo_sucursales_ya_ofrecidas"
    )
    idx_via = bloque.index(
        "_via_sucursales_ya_ofrecidas"
    )
    idx_exclusion = bloque.index(
        "not pedido_es_plegable_pp6040(pedido)"
    )

    assert idx_correo < idx_via < idx_exclusion


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
