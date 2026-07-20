from pathlib import Path


def test_app_aplica_sucursal_ofrecida_por_opcion_antes_del_fallback():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "seleccionar_sucursal_ofrecida_por_opcion" in texto
    assert "_sucursal_por_opcion = None" in texto

    idx = texto.index("_sucursal_por_opcion = seleccionar_sucursal_ofrecida_por_opcion")
    bloque = texto[idx: idx + 900]

    assert "data, candidatas_ids_check, _idx_opcion" in bloque
    assert "texto_para_sucursal = str(_idx_opcion + 1)" in bloque

    idx_fallback = texto.index("suc = _sucursal_por_opcion or detectar_sucursal")
    assert idx < idx_fallback


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
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index(
        "resultado_confirmacion_temprana = None"
    )
    fin = texto.index(
        "suc = _sucursal_por_opcion or detectar_sucursal",
        idx,
    )
    bloque = texto[idx:fin]

    assert (
        "resultado_confirmacion_temprana"
        ".requiere_operador"
        in bloque.replace("\n", "").replace(" ", "")
    )
    assert "_es_consulta_no_eleccion(" in bloque
    assert "_idx_opcion is None" in bloque

    idx_resultado = bloque.index(
        "resultado_confirmacion_temprana"
    )
    idx_fallback = bloque.index(
        "_es_consulta_no_eleccion("
    )

    assert idx_resultado < idx_fallback
