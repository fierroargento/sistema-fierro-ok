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
