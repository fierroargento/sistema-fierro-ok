from pathlib import Path


def test_app_usa_regla_central_para_completar_carga_ml_acordas():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_texto_boton = texto.index("def texto_boton_estado")
    idx_accion = texto.index("def accion_sugerida_pedido", idx_texto_boton)
    bloque_texto_boton = texto[idx_texto_boton:idx_accion]

    assert "necesita_completar_carga_etiqueta_o_seguimiento" in bloque_texto_boton
    assert 'return "Completar carga"' in bloque_texto_boton

    idx_accion = texto.index("def accion_sugerida_pedido")
    idx_primer = texto.index("def primer_paso_pendiente_carga", idx_accion)
    bloque_accion = texto[idx_accion:idx_primer]

    assert "necesita_completar_carga_etiqueta_o_seguimiento" in bloque_accion
    assert 'return "Completar carga"' in bloque_accion


def test_primer_paso_pendiente_carga_contempla_etiqueta_o_seguimiento():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx = texto.index("def primer_paso_pendiente_carga")
    idx_fin = texto.index("def accion_principal_pedido", idx)
    bloque = texto[idx:idx_fin]

    assert 'pedido.empresa_envio in ["Andreani", "Correo Argentino"]' in bloque
    assert "not pedido.etiqueta_archivo or not pedido.seguimiento" in bloque
