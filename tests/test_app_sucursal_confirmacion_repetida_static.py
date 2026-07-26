from pathlib import Path


def test_app_detector_usa_resultado_estructurado():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8")
    compacto = servicio.replace(
        "\n",
        "",
    ).replace(" ", "")

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
        "resultado_escalamiento="
        "procesar_escalamiento_fn("
        in compacto
    )
    assert (
        "deteccion="
        "resultado_escalamiento.deteccion"
        in compacto
    )
    assert (
        "ifnotdeteccion.puede_detectar:"
        in compacto
    )

    prohibidos = [
        "_correo_sucursales_ya_ofrecidas",
        "_via_sucursales_ya_ofrecidas",
        "_puede_detectar_sucursal",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_transicion_centraliza_excepcion_de_repetidos():
    app = Path("app.py").read_text(encoding="utf-8")
    flujo_cp = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8-sig")
    servicio = Path(
        "services/workflow_transicion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")
    notificacion = Path(
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
        "ejecutar_transicion_ml_tras_confirmacion_sucursal("
        in notificacion
    )
    assert (
        "continuar_si_motivo_repetido=True"
        in notificacion
    )
    assert "mensaje_automatico_repetido" not in app
    assert "mensaje_automatico_repetido" not in flujo_cp

    assert "continuar_si_motivo_repetido" in servicio
    assert (
        '"repetido" in motivo_normalizado'
        in servicio
    )
