from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    idx = APP.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_confirmacion_via_cargo_usa_helper_resumen_sucursal():
    bloque = _bloque_confirmacion_via_cargo()

    assert "agregar_marca_resumen_sucursal_confirmada" in bloque
    assert "Sucursal confirmada por opción" not in bloque


def test_confirmacion_via_cargo_sigue_usando_aplicacion_operativa():
    bloque = _bloque_confirmacion_via_cargo()

    assert "aplicar_sucursal_elegida_al_pedido" in bloque
    assert "services.workflow_logistica_sucursal" in bloque
