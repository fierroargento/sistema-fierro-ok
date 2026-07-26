from pathlib import Path


def test_app_delega_regla_detector_correo_y_pp6040():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8")

    assert (
        "from services.workflow_sucursal_decision import ("
        in app
    )
    assert (
        "procesar_escalamiento_fn=("
        in app
    )
    assert (
        "procesar_escalamiento_consulta_sucursal"
        in app
    )
    assert "pedido_es_plegable_pp6040" in app
    assert (
        "if not deteccion.puede_detectar:"
        in servicio
    )
    assert (
        "if deteccion.correo_ofrecidas:"
        in servicio
    )

    prohibidos = [
        "_correo_sucursales_ya_ofrecidas",
        "_via_sucursales_ya_ofrecidas",
        "_puede_detectar_sucursal",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio
