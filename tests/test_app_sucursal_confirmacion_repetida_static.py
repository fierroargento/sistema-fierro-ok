from pathlib import Path


def test_app_detector_usa_resultado_estructurado():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index(
        "resultado_deteccion_sucursal = ("
    )
    bloque = texto[idx:idx + 700]

    assert (
        "evaluar_sucursales_ofrecidas_pedido"
        in bloque
    )
    assert (
        "pedido_es_plegable_fn=("
        in bloque
    )
    assert "pedido_es_plegable_pp6040" in bloque
    assert (
        "if resultado_deteccion_sucursal."
        "puede_detectar:"
        in bloque
    )

    prohibidos = [
        "_correo_sucursales_ya_ofrecidas",
        "_via_sucursales_ya_ofrecidas",
        "_puede_detectar_sucursal",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque


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
