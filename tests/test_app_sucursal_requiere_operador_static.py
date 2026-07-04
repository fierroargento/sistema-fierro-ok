from pathlib import Path


def test_confirmacion_sucursal_limpia_revision_correo_y_permite_envio_seguro():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_suc = texto.index("suc = detectar_sucursal(pedido, texto_para_sucursal)")
    bloque = texto[idx_suc: idx_suc + 7000]

    assert "limpiar_revision_correo_resuelta_por_sucursales" in bloque
    assert "permitir_requiere_operador=True" in bloque


def test_consulta_horarios_se_marca_despues_de_enviar_confirmacion():
    texto = Path("app.py").read_text(encoding="utf-8")

    idx_suc = texto.index("suc = detectar_sucursal(pedido, texto_para_sucursal)")
    bloque = texto[idx_suc: idx_suc + 7000]

    idx_enviar = bloque.index("ml_enviar_mensaje_acordas(")
    idx_marcar = bloque.index("marcar_consulta_horarios_retiro_pendiente")

    assert idx_enviar < idx_marcar
