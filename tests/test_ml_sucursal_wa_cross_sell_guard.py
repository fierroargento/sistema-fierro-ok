from pathlib import Path


def test_confirmar_sucursal_ml_delega_wa_cross_sell_al_service():
    app = Path("app.py").read_text(encoding="utf-8")
    flujo_cp = Path(
        "services/ia_recolector_flujo_cp.py"
    ).read_text(encoding="utf-8-sig")
    notificacion = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")
    guard = Path(
        "services/ml_sucursal_cross_sell_guard.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "notificar_sucursal_fn=("
        in app
    )
    assert (
        "notificar_sucursal_detectada_ml"
        in app
    )
    assert "notificar_sucursal_fn(" in flujo_cp
    assert (
        "intentar_wa_cross_sell_tras_sucursal_ml"
        in notificacion
    )
    assert (
        'motivo="sucursal_confirmada_ml"'
        in notificacion
    )
    assert (
        "CROSS-SELL/WA pendiente tras confirmar "
        "sucursal ML"
        not in app
    )
    assert (
        "CROSS-SELL/WA error tras confirmar "
        "sucursal ML"
        not in app
    )
    assert "PREFIJO_WA_PENDIENTE" in guard


def test_autoavance_etiqueta_lista_delega_bloqueo_cross_sell_al_service():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "debe_bloquear_autoavance_etiqueta_lista_por_cross_sell" in texto
    assert "aplicar_reversion_autoavance_si_corresponde" in texto
    assert "def _debe_bloquear_autoavance_etiqueta_lista_por_cross_sell" not in texto
    assert "def _revertir_autoavance_etiqueta_lista_por_cross_sell" not in texto
    assert "autoavance a Etiqueta Lista revertido" not in texto
