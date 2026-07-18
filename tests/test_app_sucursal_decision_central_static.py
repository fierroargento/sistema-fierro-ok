from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    idx = APP.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_confirmacion_via_cargo_delega_decision_y_fallback_al_servicio():
    bloque = _bloque_confirmacion_via_cargo()

    assert "services.workflow_sucursal_decision" in bloque
    assert (
        "decidir_sucursal_via_cargo_para_pedido"
        in bloque
    )
    assert "decision_sucursal.seleccionada" in bloque
    assert "log_error_fn=" in bloque
    assert "DecisionSucursal" not in bloque
    assert (
        "seleccionar_sucursal_ofrecida_por_opcion"
        not in bloque
    )

def test_confirmacion_via_cargo_delega_aplicacion_operativa_y_resumen():
    bloque = _bloque_confirmacion_via_cargo()

    assert (
        "aplicar_decision_sucursal_al_pedido"
        in bloque
    )
    assert "DecisionSucursal" not in bloque
    assert (
        "agregar_marca_resumen_sucursal_confirmada"
        not in bloque
    )

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
