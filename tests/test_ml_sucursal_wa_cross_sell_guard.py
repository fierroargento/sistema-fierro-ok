from pathlib import Path


def test_confirmar_sucursal_ml_intenta_wa_cross_sell():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert 'motivo="sucursal_confirmada_ml"' in texto
    assert "wa_auto_iniciar_desde_ml_si_corresponde" in texto
    assert "CROSS-SELL/WA pendiente tras confirmar sucursal ML" in texto
    assert "CROSS-SELL/WA error tras confirmar sucursal ML" in texto


def test_autoavance_etiqueta_lista_respeta_bloqueo_cross_sell():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "def _debe_bloquear_autoavance_etiqueta_lista_por_cross_sell" in texto
    assert "debe_bloquear_etiqueta_lista_por_cross_sell" in texto
    assert "def _revertir_autoavance_etiqueta_lista_por_cross_sell" in texto
    assert "autoavance a Etiqueta Lista revertido" in texto
    assert "bloquear_cross_sell" in texto
    assert "getattr(pedido, \"estado\", None) == Estado.ETIQUETA_LISTA" in texto
