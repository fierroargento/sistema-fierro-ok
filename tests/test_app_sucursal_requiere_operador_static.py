from pathlib import Path


def test_confirmacion_sucursal_limpia_revision_correo_y_permite_envio_seguro():
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
    assert (
        "notificar_sucursal_fn=("
        in app
    )
    assert (
        "notificar_sucursal_detectada_ml"
        in app
    )
    assert "aplicar_sucursal_fn(" in flujo_cp
    assert "notificar_sucursal_fn(" in flujo_cp

    servicio_logistica = Path(
        "services/workflow_logistica_sucursal.py"
    ).read_text(encoding="utf-8-sig")
    servicio_transicion = Path(
        "services/workflow_transicion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")
    servicio_notificacion = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "ejecutar_transicion_ml_tras_confirmacion_sucursal("
        in servicio_notificacion
    )
    assert (
        "limpiar_revision_correo_resuelta_por_sucursales"
        in servicio_logistica
    )
    assert (
        "permitir_requiere_operador=True"
        in servicio_transicion
    )


def test_consulta_horarios_se_marca_despues_de_transicion():
    servicio = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    idx_enviar = servicio.index(
        "ejecutar_transicion_ml_tras_confirmacion_sucursal("
    )
    idx_marcar = servicio.index(
        "marcar_consulta_horarios_retiro_pendiente("
    )

    assert idx_enviar < idx_marcar
