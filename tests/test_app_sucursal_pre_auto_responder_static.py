from pathlib import Path


def test_flujo_comun_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_servicio = texto.index(
        "procesar_post_codigo_postal_recolector("
    )
    idx_resultado = texto.index(
        "resultado_confirmacion_temprana = (",
        idx_servicio,
    )
    idx_fallback = texto.index(
        "# DETECTAR SUCURSAL",
        idx_resultado,
    )

    assert idx_servicio < idx_resultado < idx_fallback

    bloque = texto[idx_servicio:idx_fallback]

    assert (
        "orquestar_confirmacion_fn=("
        in bloque
    )
    assert (
        "orquestar_confirmacion_sucursal_temprana"
        in bloque
    )
    assert (
        "despacho_completo_fn=despacho_completo"
        in bloque
    )
    assert "actualizar_estado_automatico" in bloque
    assert "db_session=db.session" in bloque
    assert (
        "es_afirmativo_fn=("
        in bloque
    )
    assert "es_afirmativo_sucursal" in bloque
    assert (
        "auto_responder_fn=("
        in bloque
    )
    assert (
        "ia_auto_responder_post_analisis"
        in bloque
    )
    assert (
        "resultado_post_cp.confirmacion"
        in bloque.replace("\n", "").replace(" ", "")
    )
    assert (
        "if resultado_post_cp.finalizar_analisis:"
        in bloque
    )

    assert (
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida("
        not in bloque
    )
    assert (
        "planificar_post_confirmacion_sucursal("
        not in bloque
    )
    assert (
        "ejecutar_estado_y_persistencia_"
        "post_confirmacion("
        not in bloque
    )

def test_resolucion_sucursal_delega_aplicacion_operativa():
    texto = Path(
        "services/workflow_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    idx = texto.index(
        "def resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida"
    )
    fin = texto.find("\ndef ", idx + 1)
    if fin == -1:
        fin = len(texto)
    bloque = texto[idx:fin]

    assert (
        "services.workflow_logistica_sucursal"
        in texto
    )
    assert (
        "aplicar_decision_sucursal_al_pedido"
        in bloque
    )
    assert (
        "if not aplicar_decision_sucursal_al_pedido("
        in bloque
    )
    assert "pedido," in bloque
    assert "decision_sucursal," in bloque
    assert 'transporte="Vía Cargo"' in bloque
    assert (
        "aplicar_sucursal_elegida_al_pedido"
        not in bloque
    )
    assert "pedido.sucursal_nombre = suc.get" not in bloque
    assert 'pedido.tipo_entrega = "Sucursal"' not in bloque



def test_flujo_comun_confirma_ml_transiciona_wa_y_luego_cross_sell():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_comun.py"
    ).read_text(encoding="utf-8")

    idx = app.index(
        "resultado_flujo_comun = ("
    )
    fin = app.index(
        "return resultado_flujo_comun.respuesta_analisis",
        idx,
    )
    bloque_app = app[idx:fin]

    assert (
        "procesar_flujo_comun_recolector("
        in bloque_app
    )
    assert (
        "orquestar_confirmacion_fn=("
        in bloque_app
    )
    assert (
        "orquestar_confirmacion_sucursal_comun_ml"
        in bloque_app
    )
    assert (
        "puede_enviar_fn=puede_enviar_mensaje"
        in bloque_app
    )
    assert (
        "ml_enviar_mensaje_acordas"
        in bloque_app
    )
    assert (
        "registrar_envio_automatico"
        in bloque_app
    )
    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml"
        in bloque_app
    )
    assert (
        "wa_auto_iniciar_desde_ml_si_corresponde"
        in bloque_app
    )
    assert (
        "ia_auto_responder_post_analisis"
        in bloque_app
    )

    idx_procesar = servicio.index(
        "procesar_resultado_fn("
    )
    idx_orquestar = servicio.index(
        "orquestar_confirmacion_fn("
    )
    idx_finalizada = servicio.index(
        "if resultado_orquestacion.finalizada:"
    )
    idx_auto = servicio.index(
        "auto_responder_fn(pedido)"
    )

    assert (
        idx_procesar
        < idx_orquestar
        < idx_finalizada
        < idx_auto
    )


def test_cross_sell_se_intenta_aunque_ml_se_omita_por_canal_manager():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_comun.py"
    ).read_text(encoding="utf-8")

    idx = app.index(
        "resultado_flujo_comun = ("
    )
    fin = app.index(
        "return resultado_flujo_comun.respuesta_analisis",
        idx,
    )
    bloque_app = app[idx:fin]

    assert (
        "intentar_cross_sell_fn=("
        in bloque_app
    )
    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml"
        in bloque_app
    )
    assert (
        "intentar_cross_sell_fn=("
        in servicio
    )

    # La decisión concreta sigue perteneciendo a los
    # servicios especializados de confirmación.
    assert (
        "if plan_confirmacion_comun."
        "intentar_cross_sell:"
        not in servicio
    )
    assert (
        "[CROSS-SELL-ML-WA]"
        not in servicio
    )


def test_flujo_comun_retorna_resultado_sucursal_confirmada():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_comun.py"
    ).read_text(encoding="utf-8")

    assert (
        "return resultado_flujo_comun.respuesta_analisis"
        in app
    )
    assert (
        "if resultado_orquestacion.finalizada:"
        in servicio
    )
    assert (
        "respuesta_flujo=("
        in servicio
    )
    assert (
        "resultado_orquestacion"
        in servicio
    )
    assert (
        ".respuesta_flujo"
        in servicio
    )

    prohibidos = [
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida(",
        "planificar_post_confirmacion_sucursal(",
        "ejecutar_transicion_ml_tras_"
        "confirmacion_sucursal(",
        "ejecutar_estado_y_persistencia_"
        "post_confirmacion(",
        "finalizar_confirmacion_sucursal_persistida(",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_consumidores_confirmacion_inyectan_afirmativo():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_comun.py"
    ).read_text(encoding="utf-8")

    assert (
        "from modules.whatsapp.text_utils import ("
        in app
    )
    assert (
        "es_afirmativo as es_afirmativo_sucursal"
        in app
    )

    compacto_app = app.replace(
        "\n",
        "",
    ).replace(" ", "")

    # Una inyección para confirmación temprana y otra
    # para el flujo común extraído.
    assert compacto_app.count(
        "es_afirmativo_fn=(es_afirmativo_sucursal)"
    ) == 2

    compacto_servicio = servicio.replace(
        "\n",
        "",
    ).replace(" ", "")

    assert (
        "es_afirmativo_fn=(es_afirmativo_fn)"
        in compacto_servicio
    )


def test_analizador_no_devuelve_respuestas_flask():
    texto = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = texto.index(
        "def ia_analizar_ultimo_mensaje_pedido("
    )
    fin = texto.index(
        "\ndef ia_auto_responder_post_analisis(",
        inicio,
    )
    bloque = texto[inicio:fin]

    assert "redirect(" not in bloque
    assert "url_for(" not in bloque
    assert (
        '"estado": "sucursal_confirmada"'
        in bloque
    )
    assert (
        '"sucursal_confirmada": True'
        in bloque
    )


def test_ruta_manual_convierte_confirmacion_en_redirect():
    texto = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = texto.index(
        "resultado = ia_analizar_ultimo_mensaje_pedido("
    )
    fin = texto.index(
        "\n@app.",
        inicio,
    )
    bloque = texto[inicio:fin]

    idx_confirmada = bloque.index(
        'if resultado.get("sucursal_confirmada"):'
    )
    idx_auto = bloque.index(
        "ia_auto_responder_post_analisis(pedido)"
    )

    assert idx_confirmada < idx_auto
    assert (
        "Sucursal confirmada operativamente."
        in bloque
    )
    assert (
        "No se reenvio confirmacion automatica"
        in bloque
    )
