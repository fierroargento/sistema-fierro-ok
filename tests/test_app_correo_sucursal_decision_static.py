from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def _bloque_detectar_sucursal():
    idx = APP.index("def detectar_sucursal(pedido, mensaje):")
    fin = APP.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return APP[idx:fin]


def test_detectar_sucursal_correo_usa_decision_central_con_detector_viejo():
    bloque = _bloque_detectar_sucursal()

    assert "services.workflow_sucursal_decision" in bloque
    assert "decidir_sucursal_correo_ofrecida" in bloque
    assert "detector_correo_fn=detectar_sucursal_correo_ofrecida" in bloque
    assert "decision_correo.seleccionada" in bloque


def test_detectar_sucursal_correo_mantiene_fallback_viejo():
    bloque = _bloque_detectar_sucursal()

    assert "services.correo_sucursales_eleccion" in bloque
    assert "detectar_sucursal_correo_ofrecida(pedido, mensaje)" in bloque


def test_detectar_sucursal_correo_no_manda_mensajes_ni_hace_commit():
    bloque = _bloque_detectar_sucursal()

    prohibidos = [
        "db.session.commit",
        "ml_enviar",
        "wa_enviar",
        "wa_auto",
        "registrar_envio_automatico",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
