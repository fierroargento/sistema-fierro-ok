from pathlib import Path


def _bloque_analisis_ultimo_mensaje():
    texto = Path("app.py").read_text(encoding="utf-8")
    idx = texto.index(
        "def ia_analizar_ultimo_mensaje_pedido("
    )
    fin = texto.index(
        "\ndef ia_auto_responder_post_analisis(",
        idx,
    )
    return texto[idx:fin]


def test_app_delega_opcion_via_antes_del_fallback():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8")

    assert (
        "procesar_flujo_codigo_postal_recolector("
        in app
    )
    assert (
        "orquestar_confirmacion_temprana_fn=("
        in app
    )
    assert (
        "detectar_sucursal_fn="
        "detectar_sucursal_correo_para_flujo"
        in app
    )

    idx_confirmacion = servicio.index(
        "resultado_post_cp = procesar_post_cp_fn("
    )
    idx_deteccion = servicio.index(
        "deteccion = resultado_escalamiento.deteccion"
    )
    idx_fallback = servicio.index(
        "sucursal = detectar_sucursal_fn("
    )

    assert (
        idx_confirmacion
        < idx_deteccion
        < idx_fallback
    )
    assert (
        "if deteccion.correo_ofrecidas:"
        in servicio
    )

    prohibidos = [
        "_idx_opcion",
        "_sucursal_por_opcion",
        "candidatas_ids_check",
        "extraer_opcion_sucursal_explicita",
        "normalizar_numero_opcion_sucursal",
        "seleccionar_sucursal_ofrecida_por_opcion",
        "texto_para_sucursal = str(",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_app_no_duplica_confirmacion_afirmativa_unica():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_comun.py"
    ).read_text(encoding="utf-8")

    assert (
        "es_afirmativo(_texto_confirmacion)"
        not in app
    )
    assert 'texto_para_sucursal = "1"' not in app

    compacto_app = app.replace(
        "\n",
        "",
    ).replace(" ", "")

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


def test_app_escalamiento_consulta_delega_en_servicio():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8")
    compacto = servicio.replace(
        "\n",
        "",
    ).replace(" ", "")

    assert (
        "procesar_escalamiento_fn=("
        in app
    )
    assert (
        "procesar_escalamiento_consulta_sucursal"
        in app
    )
    assert (
        "pedido_es_plegable_fn=("
        in app
    )
    assert (
        "es_consulta_no_eleccion_fn=("
        in app
    )
    assert "_es_consulta_no_eleccion" in app

    assert (
        "resultado_escalamiento="
        "procesar_escalamiento_fn("
        in compacto
    )
    assert (
        "resultado_post_cp.confirmacion"
        in servicio
    )
    assert (
        "ifresultado_escalamiento."
        "finalizar_analisis:"
        in compacto
    )
    assert (
        "deteccion="
        "resultado_escalamiento.deteccion"
        in compacto
    )

    prohibidos = [
        "pedido.ml_mensajes_pendientes = True",
        "pedido.ia_requiere_operador = True",
        "Cliente consultó sobre sucursal:",
        "_idx_opcion",
        "_sucursal_por_opcion",
        "candidatas_ids_check",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio
