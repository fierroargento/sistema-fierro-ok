from pathlib import Path


def test_flujo_comun_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_texto = texto.index(
        "_texto_logistica = texto_ultimo or texto"
    )
    idx_orquestador = texto.index(
        "orquestar_confirmacion_sucursal_temprana(",
        idx_texto,
    )
    idx_auto = texto.index(
        "ia_auto_responder_post_analisis(pedido)",
        idx_orquestador,
    )

    assert idx_texto < idx_orquestador < idx_auto

    bloque = texto[idx_texto:idx_auto]

    assert (
        "resultado_orquestacion_temprana = ("
        in bloque
    )
    assert (
        "despacho_completo_fn=despacho_completo"
        in bloque
    )
    assert (
        "actualizar_estado_fn=("
        in bloque
    )
    assert "actualizar_estado_automatico" in bloque
    assert "db_session=db.session" in bloque
    assert (
        "es_afirmativo_fn=es_afirmativo_sucursal"
        in bloque
    )
    assert (
        "resultado_confirmacion_temprana = ("
        in bloque
    )
    assert (
        ".confirmacion"
        in bloque
    )
    assert (
        "if resultado_orquestacion_temprana.persistida:"
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
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_procesar = texto.index(
        "procesar_resultado_recolector(",
        texto.index(
            "resultado = analizar_datos_cliente_"
            "ml_acordas("
        ),
    )
    idx_orquestador = texto.index(
        "orquestar_confirmacion_sucursal_comun_ml(",
        idx_procesar,
    )
    idx_return = texto.index(
        ".respuesta_flujo",
        idx_orquestador,
    )
    idx_auto = texto.index(
        "ia_auto_responder_post_analisis(pedido)",
        idx_return,
    )

    assert (
        idx_procesar
        < idx_orquestador
        < idx_return
        < idx_auto
    )

    bloque = texto[idx_orquestador:idx_auto]

    assert (
        "puede_enviar_fn=puede_enviar_mensaje"
        in bloque
    )
    assert (
        "enviar_mensaje_fn="
        "ml_enviar_mensaje_acordas"
        in bloque
    )
    assert "registrar_envio_automatico" in bloque
    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml"
        in bloque
    )
    assert (
        "wa_auto_iniciar_desde_ml_si_corresponde"
        in bloque
    )

def test_cross_sell_se_intenta_aunque_ml_se_omita_por_canal_manager():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index(
        "resultado_orquestacion_comun = ("
    )
    fin = texto.index(
        "if resultado and resultado.get",
        idx,
    )
    bloque = texto[idx:fin]

    assert (
        "orquestar_confirmacion_sucursal_comun_ml("
        in bloque
    )
    assert (
        "intentar_cross_sell_fn=("
        in bloque
    )
    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml"
        in bloque
    )

    # Las decisiones y errores del cross-sell pertenecen
    # al servicio de finalización, no a app.py.
    assert (
        "if plan_confirmacion_comun."
        "intentar_cross_sell:"
        not in bloque
    )
    assert (
        "[CROSS-SELL-ML-WA]"
        not in bloque
    )


def test_flujo_comun_retorna_resultado_sucursal_confirmada():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index(
        "resultado_orquestacion_comun = ("
    )
    fin = texto.index(
        "if resultado and resultado.get",
        idx,
    )
    bloque = texto[idx:fin]

    assert (
        "if resultado_orquestacion_comun.finalizada:"
        in bloque
    )
    assert (
        "resultado_orquestacion_comun"
        ".respuesta_flujo"
        in bloque.replace("\n", "").replace(" ", "")
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
        "ejecutar_transicion_ml_tras_"
        "confirmacion_sucursal("
        not in bloque
    )
    assert (
        "ejecutar_estado_y_persistencia_"
        "post_confirmacion("
        not in bloque
    )
    assert (
        "finalizar_confirmacion_sucursal_persistida("
        not in bloque
    )


def test_consumidores_confirmacion_inyectan_afirmativo():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert (
        "from modules.whatsapp.text_utils import ("
        in texto
    )
    assert (
        "es_afirmativo as es_afirmativo_sucursal"
        in texto
    )
    assert texto.count(
        "es_afirmativo_fn=es_afirmativo_sucursal"
    ) == 2
