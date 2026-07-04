from pathlib import Path


DOC = Path("docs/auditoria-centralizacion/03-decision-sucursales.md").read_text(encoding="utf-8")


def test_documenta_decision_sucursales():
    assert "Decision de arquitectura - Sucursales" in DOC
    assert "services/workflow/sucursal_decision.py" in DOC
    assert "services/workflow/transicion_ml_wa.py" in DOC


def test_documenta_regla_canal_manager_no_bloquea_operacion():
    assert "Canal Manager puede bloquear mensajes" in DOC
    assert "No puede bloquear guardar sucursal" in DOC


def test_documenta_funciones_base_de_mensajes_sucursales():
    assert "normalizar_numero_opcion_sucursal" in DOC
    assert "extraer_opcion_sucursal_explicita" in DOC
    assert "seleccionar_sucursal_ofrecida_por_opcion" in DOC


def test_documenta_tests_minimos_de_sucursal():
    for caso in [
        "Sucursal Nro 2",
        "opcion 2",
        "la 2",
        "sucursal unica ofrecida",
        "mensaje mixto",
        "opcion fuera de rango",
        "idempotencia",
    ]:
        assert caso in DOC
