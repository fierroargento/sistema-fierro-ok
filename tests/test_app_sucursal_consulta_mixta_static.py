from pathlib import Path


def _slice_detectar_sucursal():
    texto = Path("app.py").read_text(
        encoding="utf-8"
    )
    inicio = texto.index(
        "def detectar_sucursal(pedido, mensaje):"
    )
    fin = texto.find("\ndef ", inicio + 1)
    if fin == -1:
        fin = len(texto)
    return texto[inicio:fin]


def test_correo_delega_decision_y_conserva_fallback():
    bloque = _slice_detectar_sucursal()

    idx_decision = bloque.index(
        "decision_correo = "
        "decidir_sucursal_correo_ofrecida("
    )
    idx_seleccionada = bloque.index(
        "decision_correo.seleccionada",
        idx_decision,
    )
    idx_fallback = bloque.index(
        "return detectar_sucursal_correo_ofrecida(",
        idx_seleccionada,
    )

    assert (
        idx_decision
        < idx_seleccionada
        < idx_fallback
    )
    assert (
        "detector_correo_fn="
        "detectar_sucursal_correo_ofrecida"
        in bloque
    )


def test_detector_sucursal_queda_exclusivo_de_correo():
    bloque = _slice_detectar_sucursal()

    assert (
        'if "correo" not in transporte_actual:'
        in bloque
    )
    assert "via_cargo_sucursales.json" not in bloque
    assert "[VIA CARGO]" not in bloque


def test_confirmacion_sucursal_contempla_consulta_horarios():
    texto = Path("app.py").read_text(
        encoding="utf-8"
    )

    idx_suc = texto.index(
        "suc = detectar_sucursal("
    )
    bloque = texto[idx_suc:idx_suc + 5000]

    assert (
        "agregar_respuesta_neutra_horarios_retiro"
        in bloque
    )
    assert (
        "marcar_consulta_horarios_retiro_pendiente"
        in bloque
    )
