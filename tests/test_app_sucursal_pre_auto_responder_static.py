from pathlib import Path


def test_flujo_comun_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    nombre_nuevo = (
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida"
    )
    nombre_legacy = (
        "confirmar_sucursal_via_cargo_"
        "ofrecida_sin_responder"
    )

    assert (
        "from services.workflow_confirmacion_sucursal import ("
        in texto
    )
    assert nombre_nuevo in texto
    assert nombre_legacy not in texto

    idx_texto_logistica = texto.index(
        "_texto_logistica = texto_ultimo or texto"
    )
    idx_confirma = texto.index(
        nombre_nuevo,
        idx_texto_logistica,
    )
    idx_auto = texto.index(
        "ia_auto_responder_post_analisis(pedido)",
        idx_confirma,
    )

    assert (
        idx_texto_logistica
        < idx_confirma
        < idx_auto
    )

    bloque = texto[idx_texto_logistica:idx_auto]
    assert (
        "resultado_confirmacion_temprana = ("
        in bloque
    )
    assert (
        "plan_confirmacion_temprana = ("
        in bloque
    )
    assert (
        "planificar_post_confirmacion_sucursal("
        in bloque
    )
    assert (
        "flujo=FLUJO_CONFIRMACION_TEMPRANA"
        in bloque
    )
    assert (
        "resultado_persistencia_temprana = ("
        in bloque
    )
    assert (
        "ejecutar_estado_y_persistencia_"
        "post_confirmacion("
        in bloque
    )
    assert (
        "plan=plan_confirmacion_temprana"
        in bloque
    )
    assert (
        "actualizar_estado_fn=("
        in bloque
    )
    assert (
        "actualizar_estado_automatico"
        in bloque
    )
    assert "db_session=db.session" in bloque
    assert (
        "if resultado_persistencia_temprana.exitosa:"
        in bloque
    )
    assert (
        "if plan_confirmacion_temprana."
        "actualizar_estado:"
        not in bloque
    )
    assert (
        "if plan_confirmacion_temprana.persistir:"
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


def test_wrapper_confirmacion_delega_resultado_estructurado():
    texto = Path(
        "services/workflow_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    idx = texto.index(
        "def confirmar_sucursal_via_cargo_"
        "ofrecida_sin_persistir"
    )
    fin = texto.find("\ndef ", idx + 1)
    if fin == -1:
        fin = len(texto)
    bloque = texto[idx:fin]

    assert (
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida"
        in bloque
    )
    assert "return resultado.confirmada" in bloque
    assert (
        "aplicar_decision_sucursal_al_pedido"
        not in bloque
    )

def test_flujo_comun_confirma_ml_transiciona_wa_y_luego_cross_sell():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_guardar = texto.index(
        "ia_guardar_resultado_recolector("
        "pedido, texto, resultado)"
    )
    idx_confirma = texto.index(
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida",
        idx_guardar,
    )
    idx_transicion = texto.index(
        "ejecutar_transicion_ml_tras_"
        "confirmacion_sucursal(",
        idx_confirma,
    )
    idx_cross = texto.index(
        "intentar_wa_cross_sell_tras_sucursal_ml(",
        idx_transicion,
    )
    idx_return = texto.index(
        '"estado": "sucursal_confirmada"',
        idx_cross,
    )

    assert (
        idx_confirma
        < idx_transicion
        < idx_cross
        < idx_return
    )

    bloque_confirmacion = texto[
        idx_guardar:idx_transicion
    ]
    assert (
        "resultado_confirmacion_comun = ("
        in bloque_confirmacion
    )
    assert (
        "plan_confirmacion_comun = ("
        in bloque_confirmacion
    )
    assert (
        "planificar_post_confirmacion_sucursal("
        in bloque_confirmacion
    )
    assert (
        "flujo=FLUJO_CONFIRMACION_COMUN_ML"
        in bloque_confirmacion
    )
    assert (
        "if plan_confirmacion_comun.confirmada:"
        in bloque_confirmacion
    )

    bloque_transicion = texto[
        idx_transicion:idx_cross
    ]
    assert (
        "plan_confirmacion_comun"
        ".mensaje_transicion_ml"
        in bloque_transicion.replace(
            "\n",
            "",
        ).replace(" ", "")
    )
    assert (
        "puede_enviar_fn=puede_enviar_mensaje"
        in bloque_transicion
    )
    assert (
        "enviar_mensaje_fn="
        "ml_enviar_mensaje_acordas"
        in bloque_transicion
    )
    assert (
        "registrar_envio_fn=("
        in bloque_transicion
    )
    assert "registrar_envio_automatico" in bloque_transicion

def test_cross_sell_se_intenta_aunque_ml_se_omita_por_canal_manager():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_transicion = texto.index(
        "ejecutar_transicion_ml_tras_"
        "confirmacion_sucursal("
    )
    idx_cross = texto.index(
        "intentar_wa_cross_sell_tras_sucursal_ml(",
        idx_transicion,
    )
    idx_return = texto.index(
        '"estado": "sucursal_confirmada"',
        idx_cross,
    )

    bloque_transicion = texto[
        idx_transicion:idx_cross
    ]
    bloque_cross = texto[
        idx_cross:idx_return
    ]

    assert (
        "puede_enviar_fn=puede_enviar_mensaje"
        in bloque_transicion
    )
    assert (
        "enviar_mensaje_fn="
        "ml_enviar_mensaje_acordas"
        in bloque_transicion
    )
    assert "registrar_envio_automatico" in bloque_transicion
    assert "if permitido_ml:" not in bloque_transicion

    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml("
        in bloque_cross
    )
    assert "plan_confirmacion_comun" in bloque_cross
    assert ".motivo_cross_sell" in bloque_cross


def test_flujo_comun_retorna_resultado_sucursal_confirmada():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_guardar = texto.index(
        "ia_guardar_resultado_recolector("
        "pedido, texto, resultado)"
    )
    idx_confirma = texto.index(
        "resolver_confirmacion_sucursal_"
        "via_cargo_ofrecida",
        idx_guardar,
    )
    idx_return = texto.index(
        '"estado": "sucursal_confirmada"',
        idx_confirma,
    )
    bloque = texto[
        idx_confirma:idx_return + 300
    ]

    assert (
        "if plan_confirmacion_comun.actualizar_estado:"
        in bloque
    )
    assert "actualizar_estado_automatico(pedido)" in bloque
    assert (
        "if plan_confirmacion_comun.persistir:"
        in bloque
    )
    assert "db.session.commit()" in bloque
    assert (
        "if plan_confirmacion_comun.intentar_cross_sell:"
        in bloque
    )
    assert '"estado": "sucursal_confirmada"' in bloque
    assert '"sucursal_confirmada": True' in bloque


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
