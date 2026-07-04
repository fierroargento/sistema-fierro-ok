from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_confirmacion_via_cargo():
    idx = APP.index("def confirmar_sucursal_via_cargo_ofrecida_sin_responder")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_confirmacion_via_cargo_usa_aplicacion_operativa_de_sucursal():
    bloque = _bloque_confirmacion_via_cargo()

    assert "services.workflow_logistica_sucursal" in bloque
    assert "aplicar_sucursal_elegida_al_pedido" in bloque
    assert 'transporte="Vía Cargo"' in bloque


def test_confirmacion_via_cargo_mantiene_deteccion_vieja_por_ahora():
    bloque = _bloque_confirmacion_via_cargo()

    assert "extraer_opcion_sucursal_explicita" in bloque
    assert "normalizar_numero_opcion_sucursal" in bloque
    assert "seleccionar_sucursal_ofrecida_por_opcion" in bloque


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
