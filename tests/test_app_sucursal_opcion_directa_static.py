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
    bloque = _bloque_analisis_ultimo_mensaje()

    idx_resolver = bloque.index(
        "resultado_confirmacion_temprana = ("
    )
    idx_fallback = bloque.index(
        "suc = detectar_sucursal("
    )

    assert idx_resolver < idx_fallback

    bloque_fallback = bloque[
        idx_resolver:idx_fallback + 300
    ]
    compacto = bloque_fallback.replace(
        "\n",
        "",
    ).replace(" ", "")

    assert (
        "resultado_deteccion_sucursal"
        ".correo_ofrecidas"
        in compacto
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
        assert prohibido not in bloque


def test_app_no_duplica_confirmacion_afirmativa_unica():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert (
        "es_afirmativo(_texto_confirmacion)"
        not in texto
    )
    assert 'texto_para_sucursal = "1"' not in texto
    compacto = texto.replace("\n", "").replace(
        " ",
        "",
    )

    assert texto.count(
        "es_afirmativo_fn=es_afirmativo_sucursal"
    ) == 1
    assert compacto.count(
        "es_afirmativo_fn=(es_afirmativo_sucursal)"
    ) == 1


def test_app_escalamiento_consulta_delega_en_servicio():
    bloque = _bloque_analisis_ultimo_mensaje()

    idx = bloque.index(
        "resultado_escalamiento_sucursal = ("
    )
    fin = bloque.index(
        "suc = detectar_sucursal(",
        idx,
    )
    escalamiento = bloque[idx:fin]
    compacto = escalamiento.replace(
        "\n",
        "",
    ).replace(" ", "")

    assert (
        "procesar_escalamiento_consulta_sucursal("
        in escalamiento
    )
    assert (
        "resultado_confirmacion_temprana"
        in escalamiento
    )
    assert (
        "pedido_es_plegable_fn=("
        in escalamiento
    )
    assert (
        "es_consulta_no_eleccion_fn=("
        in escalamiento
    )
    assert "_es_consulta_no_eleccion" in escalamiento
    assert "db_session=db.session" in escalamiento
    assert (
        "resultado_escalamiento_sucursal.deteccion"
        in compacto
    )
    assert (
        "resultado_escalamiento_sucursal"
        ".finalizar_analisis"
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
        assert prohibido not in escalamiento
