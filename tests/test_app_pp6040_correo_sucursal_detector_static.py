from pathlib import Path


def test_pp6040_con_sucursales_correo_no_queda_excluido_del_detector():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("# DETECTAR SUCURSAL")
    bloque = texto[idx: idx + 1800]

    assert "if not pedido_es_plegable_pp6040(pedido) and _sucursales_ya_ofrecidas:" not in bloque
    assert "_correo_sucursales_ya_ofrecidas" in bloque
    assert "_via_sucursales_ya_ofrecidas" in bloque
    assert "_puede_detectar_sucursal" in bloque
    assert "_correo_sucursales_ya_ofrecidas" in bloque
    assert "not pedido_es_plegable_pp6040(pedido)" in bloque
