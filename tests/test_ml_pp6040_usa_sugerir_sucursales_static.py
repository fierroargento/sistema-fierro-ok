from pathlib import Path


def textos_flujo():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    servicio = Path(
        "services/ia_auto_respuesta_logistica.py"
    ).read_text(encoding="utf-8-sig")
    sucursales = Path(
        "services/ml_sucursales_via_cargo.py"
    ).read_text(encoding="utf-8-sig")

    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find("\ndef ", inicio + 1)
    if fin == -1:
        fin = len(app)

    return app[inicio:fin], servicio, sucursales


def test_app_delega_datos_completos_al_orquestador():
    bloque, servicio, _sucursales = textos_flujo()

    assert (
        "procesar_datos_completos_auto_respuesta_ml("
        in bloque
    )
    assert (
        "es_ml_acordas_entrega_service"
        in bloque
    )
    assert (
        "pedido_es_plegable_pp6040_service"
        in bloque
    )
    assert (
        "resultado_datos_completos.motivo"
        in bloque
    )

    assert (
        "def procesar_datos_completos_auto_respuesta_ml("
        in servicio
    )


def test_orquestador_conserva_orden_logistico():
    _bloque, servicio, _sucursales = textos_flujo()

    pos_asignacion = servicio.index(
        "procesar_asignacion_service_fn("
    )
    pos_default = servicio.index(
        "aplicar_default_service_fn("
    )
    pos_sugerencias = servicio.index(
        "enviar_sugerencia_service_fn("
    )
    pos_wa = servicio.index(
        "wa_auto_iniciar_fn("
    )

    assert (
        pos_asignacion
        < pos_default
        < pos_sugerencias
        < pos_wa
    )


def test_pp6040_asignado_no_aplica_default_via_cargo():
    _bloque, servicio, _sucursales = textos_flujo()

    pos_resultado = servicio.index(
        "resultado_asignacion.transporte_asignado"
    )
    pos_guard = servicio.index(
        "if not pp6040_transporte_asignado:",
        pos_resultado,
    )
    pos_default = servicio.index(
        "aplicar_default_service_fn(",
        pos_guard,
    )

    assert pos_resultado < pos_guard < pos_default


def test_orquestador_delega_envio_de_sucursales():
    bloque, servicio, sucursales = textos_flujo()

    assert (
        "enviar_sugerencia_service_fn("
        in servicio
    )
    assert (
        'motivo_ok="sucursales_enviadas"'
        in servicio
    )
    assert (
        'motivo_error="error_sucursales"'
        in servicio
    )
    assert (
        "if resultado_sucursales is not None:"
        in servicio
    )

    assert (
        "enviar_sugerencia_sucursales_ml("
        not in bloque
    )
    assert (
        "pedido.ia_respuesta_sugerida = mensaje"
        in sucursales
    )
    assert (
        "pedido.ml_mensajes_pendientes = False"
        in sucursales
    )
    assert "db_session.commit()" in sucursales


def test_orquestador_conserva_resultados_de_handoff():
    _bloque, servicio, _sucursales = textos_flujo()

    assert (
        '"wa_iniciado_datos_completos"'
        in servicio
    )
    assert (
        'motivo_wa or "datos_completos"'
        in servicio
    )
    assert (
        '"ia_auto_responder_post_analisis_"'
        in servicio
    )
    assert '"datos_completos"' in servicio
