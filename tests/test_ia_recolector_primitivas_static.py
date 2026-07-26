from pathlib import Path


def bloque_analizador():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_analizar_ultimo_mensaje_pedido("
    )
    fin = app.index(
        "\ndef ia_auto_responder_post_analisis(",
        inicio,
    )
    return app, app[inicio:fin]


def test_analizador_usa_hash_canonico():
    app, bloque = bloque_analizador()

    assert (
        "from services.ia_mensajes import ("
        in app
    )
    assert "ia_hash_texto_service," in app
    assert (
        "hash_texto_fn=ia_hash_texto_service"
        in bloque
    )
    assert "hash_texto_fn=ia_hash_texto," not in bloque


def test_analizador_usa_faltantes_canonicos():
    app, bloque = bloque_analizador()

    assert (
        "from services.ia_recolector_sync import ("
        in app
    )
    assert "faltantes_pedido_recolector," in app
    assert (
        "faltantes_fn=faltantes_pedido_recolector"
        in bloque
    )
    assert (
        "faltantes_fn=ia_faltantes_pedido"
        not in bloque
    )


def test_wrappers_historicos_siguen_disponibles():
    app, _ = bloque_analizador()

    assert "def ia_hash_texto(texto):" in app
    assert "def ia_faltantes_pedido(pedido):" in app

def test_analizador_usa_regla_ml_acordas_canonica():
    app, bloque = bloque_analizador()

    assert (
        "from services.logistica_defaults import ("
        in app
    )
    assert "es_ml_acordas_entrega_service," in app
    assert (
        "es_pedido_aplicable_fn="
        "es_ml_acordas_entrega_service"
        in bloque
    )
    assert (
        "es_pedido_aplicable_fn="
        "es_ml_acordas_entrega,"
        not in bloque
    )


def test_wrapper_ml_acordas_historico_sigue_disponible():
    app, _ = bloque_analizador()

    assert "def es_ml_acordas_entrega(pedido):" in app

def test_analizador_usa_detector_pp6040_canonico():
    app, bloque = bloque_analizador()

    assert (
        "from services.logistica_defaults import ("
        in app
    )
    assert (
        "pedido_es_plegable_pp6040_service,"
        in app
    )
    assert (
        "pedido_es_plegable_fn=("
        in bloque
    )
    assert (
        "pedido_es_plegable_pp6040_service"
        in bloque
    )
    assert (
        "pedido_es_plegable_pp6040\n"
        not in bloque
    )


def test_wrapper_pp6040_historico_sigue_disponible():
    app, _ = bloque_analizador()

    assert (
        "def pedido_es_plegable_pp6040(pedido):"
        in app
    )
    assert (
        "pedido_es_plegable_pp6040_contacto(pedido)"
        in app
    )


def test_analizador_usa_consulta_no_eleccion_compartida():
    app, bloque = bloque_analizador()

    assert (
        "from services.workflow_sucursal_decision "
        "import ("
        in app
    )
    assert (
        "es_consulta_no_eleccion_sucursal,"
        in app
    )
    assert (
        "es_consulta_no_eleccion_fn=("
        in bloque
    )
    assert (
        "es_consulta_no_eleccion_sucursal"
        in bloque
    )
    assert "_es_consulta_no_eleccion\n" not in bloque

    assert (
        "def _es_consulta_no_eleccion(texto):"
        in app
    )
    assert (
        "return es_consulta_no_eleccion_sucursal(texto)"
        in app
    )


def test_analizador_usa_detector_sucursal_compartido():
    app, bloque = bloque_analizador()

    assert (
        "detectar_sucursal_correo_para_flujo,"
        in app
    )
    assert (
        "detectar_sucursal_fn="
        "detectar_sucursal_correo_para_flujo"
        in bloque
    )
    assert (
        "detectar_sucursal_fn=detectar_sucursal,"
        not in bloque
    )

    assert (
        "def detectar_sucursal(pedido, mensaje):"
        in app
    )
    assert (
        "return detectar_sucursal_correo_para_flujo("
        in app
    )


def test_actualizar_estado_automatico_delega_workflow_protegido():
    app, _ = bloque_analizador()

    inicio = app.index(
        "def actualizar_estado_automatico(pedido):"
    )
    fin = app.index(
        "\ndef intentar_cross_sell_previo_seguimiento_wa(",
        inicio,
    )
    wrapper = app[inicio:fin]

    assert (
        "actualizar_estado_automatico_"
        "protegido_service("
        in wrapper
    )
    assert (
        "evento_operativo_model=EventoOperativo"
        in wrapper
    )
    assert (
        "debe_bloquear_autoavance_"
        "etiqueta_lista_por_cross_sell("
        not in wrapper
    )
    assert (
        "aplicar_reversion_autoavance_"
        "si_corresponde("
        not in wrapper
    )


def test_analizador_usa_marcador_respuesta_cliente_runtime():
    app, bloque = bloque_analizador()
    compacto = "".join(bloque.split())

    assert (
        "from modules.whatsapp.runtime import ("
        in app
    )
    assert (
        "ia_marcar_respuesta_cliente as "
        "ia_marcar_respuesta_cliente_runtime,"
        in app
    )
    assert (
        "marcar_respuesta_fn=("
        "ia_marcar_respuesta_cliente_runtime)"
        in compacto
    )
    assert (
        "marcar_respuesta_fn=("
        "ia_marcar_respuesta_cliente)"
        not in compacto
    )


def test_wrapper_respuesta_cliente_historico_sigue_disponible():
    app, _ = bloque_analizador()

    assert (
        "def ia_marcar_respuesta_cliente("
        in app
    )
