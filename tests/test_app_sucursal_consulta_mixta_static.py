from pathlib import Path


def _slice_detectar_sucursal():
    texto = Path(
        "services/workflow_sucursal_decision.py"
    ).read_text(encoding="utf-8-sig")
    inicio = texto.index(
        "def detectar_sucursal_correo_para_flujo("
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


def test_confirmacion_sucursal_delega_consulta_horarios():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    flujo_cp = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8-sig")
    servicio = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "notificar_sucursal_fn=("
        in app
    )
    assert (
        "notificar_sucursal_detectada_ml"
        in app
    )
    assert "notificar_sucursal_fn(" in flujo_cp
    assert (
        "agregar_respuesta_neutra_horarios_retiro"
        in servicio
    )
    assert (
        "marcar_consulta_horarios_retiro_pendiente"
        in servicio
    )
