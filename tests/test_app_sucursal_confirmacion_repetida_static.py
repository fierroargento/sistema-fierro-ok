from pathlib import Path


def test_app_detector_usa_resultado_estructurado():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index(
        "resultado_escalamiento_sucursal = ("
    )
    fin = texto.index(
        "suc = detectar_sucursal(",
        idx,
    )
    bloque = texto[idx:fin]
    compacto = bloque.replace(
        "\n",
        "",
    ).replace(" ", "")

    assert (
        "procesar_escalamiento_consulta_sucursal("
        in bloque
    )
    assert (
        "pedido_es_plegable_fn=("
        in bloque
    )
    assert "pedido_es_plegable_pp6040" in bloque
    assert (
        "resultado_escalamiento_sucursal.deteccion"
        in compacto
    )
    assert (
        "ifresultado_deteccion_sucursal."
        "puede_detectar:"
        in compacto
    )

    prohibidos = [
        "_correo_sucursales_ya_ofrecidas",
        "_via_sucursales_ya_ofrecidas",
        "_puede_detectar_sucursal",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque


def test_transicion_centraliza_excepcion_de_repetidos():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/workflow_transicion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    notificacion = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "notificar_sucursal_detectada_ml("
        in app
    )
    assert (
        "ejecutar_transicion_ml_tras_confirmacion_sucursal("
        in notificacion
    )
    assert (
        "continuar_si_motivo_repetido=True"
        in notificacion
    )
    assert "mensaje_automatico_repetido" not in app

    assert (
        "continuar_si_motivo_repetido"
        in servicio
    )
    assert (
        '"repetido" in motivo_normalizado'
        in servicio
    )
