from pathlib import Path


def test_app_marca_correo_sucursal_pendiente_operador_antes_de_commit():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "marcar_correo_sucursal_pendiente_operador" in texto

    posicion_marca = texto.index("marcar_correo_sucursal_pendiente_operador(pedido)")
    posicion_commit = texto.index("db.session.commit()", posicion_marca)

    assert posicion_marca < posicion_commit
