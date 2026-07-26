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
    app = Path("app.py").read_text(encoding="utf-8")
    flujo_cp = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "aplicar_sucursal_fn=("
        in app
    )
    assert (
        "aplicar_y_persistir_sucursal_detectada"
        in app
    )
    assert "aplicar_sucursal_fn(" in flujo_cp
    assert "db_session=db_session" in flujo_cp
