from pathlib import Path


def test_app_delega_regla_detector_correo_y_pp6040():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("# DETECTAR SUCURSAL")
    bloque = texto[idx:idx + 1500]

    assert (
        "services.workflow_sucursal_decision"
        in bloque
    )
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
        "resultado_deteccion_sucursal."
        "puede_detectar"
        in bloque
    )
    assert "_correo_sucursales_ya_ofrecidas" not in bloque
    assert "_via_sucursales_ya_ofrecidas" not in bloque
    assert "_puede_detectar_sucursal" not in bloque
