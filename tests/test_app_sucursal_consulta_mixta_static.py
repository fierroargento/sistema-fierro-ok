from pathlib import Path


def _slice_detectar_sucursal():
    texto = Path("app.py").read_text(encoding="utf-8")
    idx_func = texto.index("def detectar_sucursal(")
    idx_via = texto.index('with open("via_cargo_sucursales.json"', idx_func)
    return texto[idx_func:idx_via]


def test_correo_detecta_sucursal_antes_de_descartar_por_consulta():
    bloque = _slice_detectar_sucursal()

    idx_correo = bloque.index('if "correo" in transporte_actual:')
    idx_detectar = bloque.index("sucursal_correo = detectar_sucursal_correo_ofrecida", idx_correo)
    idx_consulta = bloque.index("if _es_consulta_no_eleccion(texto):", idx_detectar)

    assert idx_correo < idx_detectar < idx_consulta


def test_confirmacion_sucursal_contempla_consulta_horarios():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_suc = texto.index("detectar_sucursal(pedido, texto_para_sucursal)")
    bloque = texto[idx_suc: idx_suc + 5000]

    assert "agregar_respuesta_neutra_horarios_retiro" in bloque
    assert "marcar_consulta_horarios_retiro_pendiente" in bloque
