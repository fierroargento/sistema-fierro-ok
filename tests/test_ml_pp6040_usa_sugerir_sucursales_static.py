from pathlib import Path


def bloque_post_analisis():
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index(
        "def ia_auto_responder_post_analisis"
    )
    fin = texto.index(
        "def ia_generar_respuesta_faltantes_pedido",
        inicio,
    )
    return texto[inicio:fin]


def test_pp6040_asignado_sigue_hasta_ofrecer_sucursales():
    bloque = bloque_post_analisis()

    assert (
        "pp6040_transporte_asignado = False"
        in bloque
    )
    assert (
        "pp6040_transporte_asignado = True"
        in bloque
    )
    assert (
        "enviar_sugerencia_sucursales_ml("
        in bloque
    )
    assert (
        "sugerir_sucursales_fn=("
        in bloque
    )
    assert "sugerir_sucursales" in bloque

    pos_true = bloque.index(
        "pp6040_transporte_asignado = True"
    )
    pos_ofrecer = bloque.index(
        "enviar_sugerencia_sucursales_ml("
    )

    assert pos_true < pos_ofrecer


def test_pp6040_no_aplica_default_via_cargo_si_correo_fue_asignado():
    bloque = bloque_post_analisis()

    pos_guard = bloque.index(
        "if not pp6040_transporte_asignado:"
    )
    pos_default = bloque.index(
        "aplicar_default_via_cargo_"
        "sucursal_ml_acordas"
    )
    pos_ofrecer = bloque.index(
        "enviar_sugerencia_sucursales_ml("
    )

    assert pos_guard < pos_default < pos_ofrecer


def test_bloque_comun_delega_envio_sucursales_ml():
    bloque = bloque_post_analisis()
    servicio = Path(
        "services/ml_sucursales_via_cargo.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "enviar_sugerencia_sucursales_ml("
        in bloque
    )
    assert (
        "puede_enviar_mensaje_fn=("
        in bloque
    )
    assert (
        "enviar_mensaje_ml_fn=("
        in bloque
    )
    assert (
        "registrar_envio_automatico_fn=("
        in bloque
    )
    assert (
        'motivo_ok="sucursales_enviadas"'
        in bloque
    )
    assert (
        'motivo_error="error_sucursales"'
        in bloque
    )
    assert (
        "if resultado_sucursales is not None:"
        in bloque
    )

    assert (
        "pedido.ia_respuesta_sugerida = mensaje"
        in servicio
    )
    assert (
        "pedido.ml_mensajes_pendientes = False"
        in servicio
    )
    assert "db_session.commit()" in servicio


def test_pp6040_ml_prepara_asignacion_y_persiste_una_vez():
    bloque = bloque_post_analisis()

    inicio = bloque.index(
        "if pedido_es_plegable_pp6040(pedido):"
    )
    fin = bloque.index(
        "if not pp6040_transporte_asignado:",
        inicio,
    )
    asignacion = bloque[inicio:fin]

    assert (
        "preparar_asignacion_transporte_pedido"
        in asignacion
    )
    assert "resultado_transporte.ok" in asignacion
    assert (
        "resultado_transporte.requiere_rollback"
        in asignacion
    )
    assert "db.session.rollback()" in asignacion
    assert (
        "asignar_transporte_pedido("
        not in asignacion
    )

    pos_resumen = asignacion.index(
        "pedido.ia_resumen ="
    )
    pos_commit = asignacion.index(
        "db.session.commit()",
        pos_resumen,
    )
    pos_asignado = asignacion.index(
        "pp6040_transporte_asignado = True"
    )

    assert pos_resumen < pos_commit < pos_asignado
