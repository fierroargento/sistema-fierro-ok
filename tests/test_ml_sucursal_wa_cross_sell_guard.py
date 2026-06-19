from pathlib import Path


def test_confirmar_sucursal_ml_delega_wa_cross_sell_al_service():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "intentar_wa_cross_sell_tras_sucursal_ml" in texto
    assert 'motivo="sucursal_confirmada_ml"' in texto
    assert "CROSS-SELL/WA pendiente tras confirmar sucursal ML" not in texto
    assert "CROSS-SELL/WA error tras confirmar sucursal ML" not in texto


def test_autoavance_etiqueta_lista_delega_bloqueo_cross_sell_al_service():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "debe_bloquear_autoavance_etiqueta_lista_por_cross_sell" in texto
    assert "aplicar_reversion_autoavance_si_corresponde" in texto
    assert "def _debe_bloquear_autoavance_etiqueta_lista_por_cross_sell" not in texto
    assert "def _revertir_autoavance_etiqueta_lista_por_cross_sell" not in texto
    assert "autoavance a Etiqueta Lista revertido" not in texto
