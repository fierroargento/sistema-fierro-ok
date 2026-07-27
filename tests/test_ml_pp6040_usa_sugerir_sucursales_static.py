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
    servicio = Path(
        "services/ia_auto_respuesta_logistica.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "pp6040_transporte_asignado = False"
        in bloque
    )
    assert (
        "procesar_asignacion_transporte_pp6040("
        in bloque
    )
    assert (
        "resultado_asignacion_pp6040"
        ".transporte_asignado"
        in bloque.replace("\n", "").replace(" ", "")
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

    assert (
        "transporte_asignado=True"
        in servicio.replace("\n", "").replace(" ", "")
    )

    pos_asignacion = bloque.index(
        "procesar_asignacion_transporte_pp6040("
    )
    pos_resultado = bloque.index(
        ".transporte_asignado",
        pos_asignacion,
    )
    pos_ofrecer = bloque.index(
        "enviar_sugerencia_sucursales_ml("
    )

    assert (
        pos_asignacion
        < pos_resultado
        < pos_ofrecer
    )

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


def test_pp6040_ml_delega_asignacion_y_persistencia():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    servicio = Path(
        "services/ia_auto_respuesta_logistica.py"
    ).read_text(encoding="utf-8-sig")

    bloque = bloque_post_analisis()

    assert (
        "procesar_asignacion_transporte_pp6040("
        in bloque
    )
    assert (
        "preparar_asignacion_fn=("
        in bloque
    )
    assert (
        "preparar_asignacion_transporte_pedido"
        in bloque
    )
    assert "db_session=db.session" in bloque

    assert "resultado_transporte.ok" not in bloque
    assert (
        "resultado_transporte.requiere_rollback"
        not in bloque
    )

    assert "if resultado.ok:" in servicio
    assert "if resultado.requiere_rollback:" in servicio
    assert "db_session.rollback()" in servicio
    assert "db_session.commit()" in servicio

    pos_asignacion = bloque.index(
        "procesar_asignacion_transporte_pp6040("
    )
    pos_default_via = bloque.index(
        "aplicar_default_via_cargo_sucursal_ml_acordas"
    )
    pos_sugerencia = bloque.index(
        "enviar_sugerencia_sucursales_ml("
    )

    assert (
        pos_asignacion
        < pos_default_via
        < pos_sugerencia
    )
