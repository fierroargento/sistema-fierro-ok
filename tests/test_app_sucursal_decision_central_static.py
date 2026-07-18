from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    idx = APP.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_confirmacion_via_cargo_usa_decision_central_con_fallback():
    bloque = _bloque_confirmacion_via_cargo()

    assert "services.workflow_sucursal_decision" in bloque
    assert "decidir_sucursal_via_cargo_ofrecida" in bloque
    assert "decision_sucursal.seleccionada" in bloque
    assert "seleccionar_sucursal_ofrecida_por_opcion" in bloque


def test_confirmacion_via_cargo_mantiene_aplicacion_operativa_y_resumen():
    bloque = _bloque_confirmacion_via_cargo()

    assert "aplicar_decision_sucursal_al_pedido" in bloque
    assert "DecisionSucursal" in bloque


def test_confirmacion_via_cargo_no_manda_mensajes_externos():
    bloque = _bloque_confirmacion_via_cargo()

    prohibidos = [
        "ml_enviar_mensaje_acordas",
        "wa_auto_iniciar_desde_ml",
        "wa_enviar",
        "registrar_envio_automatico",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
