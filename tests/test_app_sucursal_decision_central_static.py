from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    idx = APP.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_confirmacion_via_cargo_usa_decision_central_de_sucursal():
    bloque = _bloque_confirmacion_via_cargo()

    assert "services.workflow_sucursal_decision" in bloque
    assert "decidir_sucursal_via_cargo_ofrecida" in bloque
    assert "decision_sucursal.seleccionada" in bloque


def test_confirmacion_via_cargo_mantiene_fallback_viejo():
    bloque = _bloque_confirmacion_via_cargo()

    assert "seleccionar_sucursal_ofrecida_por_opcion" in bloque
    assert "if not suc:" in bloque


def test_confirmacion_via_cargo_sigue_sin_depender_de_mensaje_externo():
    bloque = _bloque_confirmacion_via_cargo()

    prohibidos = [
        "ml_enviar_mensaje_acordas",
        "wa_auto_iniciar_desde_ml",
        "wa_enviar",
        "registrar_envio_automatico",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
