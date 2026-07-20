from pathlib import Path


def test_flujo_comun_confirma_sucursal_antes_de_auto_responder_ml():
    texto = Path("app.py").read_text(encoding="utf-8")

    nombre_nuevo = (
        "confirmar_sucursal_via_cargo_"
        "ofrecida_sin_persistir"
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

    idx_guardar = texto.index(
        "ia_guardar_resultado_recolector("
        "pedido, texto, resultado)"
    )
    idx_confirma = texto.index(
        nombre_nuevo,
        idx_guardar,
    )
    idx_auto = texto.index(
        "ia_auto_responder_post_analisis(pedido)",
        idx_guardar,
    )

    assert idx_guardar < idx_confirma < idx_auto

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
        "confirmar_sucursal_via_cargo_"
        "ofrecida_sin_persistir",
        idx_guardar,
    )
    idx_msg = texto.index(
        "msg_transicion_wa",
        idx_confirma,
    )
    idx_ml = texto.index(
        "ml_enviar_mensaje_acordas(",
        idx_confirma,
    )
    idx_cross = texto.index(
        "intentar_wa_cross_sell_tras_sucursal_ml(",
        idx_confirma,
    )
    idx_return = texto.index(
        '"estado": "sucursal_confirmada"',
        idx_confirma,
    )

    assert (
        idx_confirma
        < idx_msg
        < idx_ml
        < idx_cross
        < idx_return
    )

def test_cross_sell_se_intenta_aunque_ml_se_omita_por_canal_manager():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_msg = texto.index("msg_transicion_wa")
    idx_cross = texto.index("intentar_wa_cross_sell_tras_sucursal_ml(", idx_msg)
    idx_return = texto.index('"estado": "sucursal_confirmada"', idx_cross)

    bloque_ml = texto[idx_msg:idx_cross]
    bloque_cross = texto[idx_cross:idx_return]

    assert "puede_enviar_mensaje(" in bloque_ml
    assert "if permitido_ml:" in bloque_ml
    assert "ML transicion WA omitida" in bloque_ml
    assert "intentar_wa_cross_sell_tras_sucursal_ml(" in bloque_cross
    assert 'motivo="sucursal_confirmada_sin_auto_respuesta"' in bloque_cross


def test_flujo_comun_retorna_resultado_sucursal_confirmada():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_guardar = texto.index(
        "ia_guardar_resultado_recolector("
        "pedido, texto, resultado)"
    )
    idx_confirma = texto.index(
        "confirmar_sucursal_via_cargo_"
        "ofrecida_sin_persistir",
        idx_guardar,
    )
    idx_return = texto.index(
        '"estado": "sucursal_confirmada"',
        idx_confirma,
    )
    bloque = texto[
        idx_confirma:idx_return + 300
    ]

    assert "actualizar_estado_automatico(pedido)" in bloque
    assert "db.session.commit()" in bloque
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
