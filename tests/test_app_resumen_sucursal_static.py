from pathlib import Path


WORKFLOW = Path("services/workflow_confirmacion_sucursal.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    return WORKFLOW

def test_confirmacion_via_cargo_delega_resumen_en_aplicacion_operativa():
    bloque = _bloque_confirmacion_via_cargo()

    assert "aplicar_decision_sucursal_al_pedido" in bloque
    assert "Sucursal confirmada por opción" not in bloque


def test_confirmacion_via_cargo_sigue_usando_aplicacion_operativa():
    bloque = _bloque_confirmacion_via_cargo()

    assert "aplicar_decision_sucursal_al_pedido" in bloque
    assert "services.workflow_logistica_sucursal" in bloque
