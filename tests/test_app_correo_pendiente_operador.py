from pathlib import Path


def test_servicio_marca_correo_pendiente_antes_de_commit():
    texto = Path(
        "services/workflow_logistica_sucursal.py"
    ).read_text(encoding="utf-8-sig")

    posicion_marca = texto.index(
        "marcar_pendiente_fn(pedido)"
    )
    posicion_commit = texto.index(
        "db_session.commit()",
        posicion_marca,
    )

    assert posicion_marca < posicion_commit


def test_app_delega_aplicacion_sucursal_detectada():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert (
        "aplicar_y_persistir_sucursal_detectada("
        in texto
    )
    assert "db_session=db.session" in texto
