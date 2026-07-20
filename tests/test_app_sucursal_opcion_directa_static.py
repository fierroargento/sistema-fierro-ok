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
        "pedido, texto_para_sucursal)"
    )

    assert idx_resolver < idx_fallback

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
    assert texto.count(
        "es_afirmativo_fn=es_afirmativo_sucursal"
    ) == 2


def test_app_escalamiento_consulta_usa_resultado_estructurado_con_fallback():
    bloque = _bloque_analisis_ultimo_mensaje()

    idx = bloque.index(
        "resultado_confirmacion_temprana = None"
    )
    fin = bloque.index(
        "suc = detectar_sucursal("
        "pedido, texto_para_sucursal)",
        idx,
    )
    escalamiento = bloque[idx:fin]
    compacto = escalamiento.replace("\n", "").replace(
        " ",
        "",
    )

    assert (
        "resultado_confirmacion_temprana"
        ".requiere_operador"
        in compacto
    )
    assert (
        "resultado_deteccion_sucursal"
        ".via_cargo_ofrecidas"
        in compacto
    )
    assert "_es_consulta_no_eleccion(" in escalamiento

    prohibidos = [
        "_idx_opcion",
        "_sucursal_por_opcion",
        "candidatas_ids_check",
    ]

    for prohibido in prohibidos:
        assert prohibido not in escalamiento
