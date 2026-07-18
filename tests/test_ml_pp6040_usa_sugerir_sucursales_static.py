from pathlib import Path


def bloque_post_analisis():
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index("def ia_auto_responder_post_analisis")
    fin = texto.index("def ia_generar_respuesta_faltantes_pedido", inicio)
    return texto[inicio:fin]


def test_pp6040_asignado_sigue_hasta_sugerir_sucursales():
    bloque = bloque_post_analisis()

    assert "pp6040_transporte_asignado = False" in bloque
    assert "pp6040_transporte_asignado = True" in bloque
    assert "msg_sucursales = sugerir_sucursales(pedido)" in bloque

    pos_true = bloque.index("pp6040_transporte_asignado = True")
    pos_sugerir = bloque.index("msg_sucursales = sugerir_sucursales(pedido)")

    assert pos_true < pos_sugerir


def test_pp6040_no_aplica_default_via_cargo_si_correo_fue_asignado():
    bloque = bloque_post_analisis()

    pos_guard = bloque.index("if not pp6040_transporte_asignado:")
    pos_default = bloque.index("aplicar_default_via_cargo_sucursal_ml_acordas")
    pos_sugerir = bloque.index("msg_sucursales = sugerir_sucursales(pedido)")

    assert pos_guard < pos_default < pos_sugerir


def test_bloque_comun_envia_sucursales_por_ml():
    bloque = bloque_post_analisis()

    inicio = bloque.index("msg_sucursales = sugerir_sucursales(pedido)")
    fin = bloque.index('return True, "sucursales_enviadas"', inicio)
    envio = bloque[inicio:fin]

    assert "puede_enviar_mensaje(" in envio
    assert 'canal="ml"' in envio
    assert "ml_enviar_mensaje_acordas(pedido, msg_sucursales)" in envio
    assert "registrar_envio_automatico(" in envio
    assert "pedido.ia_respuesta_sugerida = msg_sucursales" in envio
    assert "pedido.ml_mensajes_pendientes = False" in envio


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
    assert "asignar_transporte_pedido(" not in asignacion

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
