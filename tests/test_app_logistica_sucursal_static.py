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
    assert "aplicar_decision_sucursal_al_pedido" in bloque
    assert 'transporte="Vía Cargo"' in bloque


def test_confirmacion_via_cargo_delega_decision_desde_opciones_del_pedido():
    bloque = _bloque_confirmacion_via_cargo()

    assert (
        "decidir_sucursal_via_cargo_para_pedido"
        in bloque
    )
    assert "sucursales_catalogo=sucursales" in bloque
    assert "log_error_fn=" in bloque
    assert (
        "extraer_opcion_sucursal_explicita"
        not in bloque
    )
    assert (
        "normalizar_numero_opcion_sucursal"
        not in bloque
    )
    assert (
        "seleccionar_sucursal_ofrecida_por_opcion"
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

def test_confirmacion_via_cargo_carga_catalogo_desde_servicio():
    bloque = _bloque_confirmacion_via_cargo()

    assert (
        "services.via_cargo_sucursales"
        in bloque
    )
    assert "cargar_sucursales_via_cargo" in bloque
    assert "if not sucursales:" in bloque
    assert (
        'with open("via_cargo_sucursales.json"'
        not in bloque
    )
    assert "json.load(" not in bloque
