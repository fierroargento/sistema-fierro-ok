from pathlib import Path


def test_selector_correo_no_activa_wa_si_origen_es_ml():
    texto = Path("modules/transportes/selector.py").read_text(encoding="utf-8")

    assert 'def sugerir_sucursales_correo_pedido(pedido, canal_origen="ml"):' in texto
    assert 'canal_origen = str(canal_origen or "ml").strip().lower()' in texto
    assert 'if canal_origen in ("wa", "whatsapp"):' in texto
    assert 'pedido.wa_estado = "falta_elegir_transporte"' in texto
    assert 'elif str(getattr(pedido, "wa_estado", "") or "").strip().lower() == "falta_elegir_transporte":' in texto
    assert 'pedido.wa_estado = ""' in texto


def test_whatsapp_pasa_canal_origen_wa_al_selector_correo():
    texto = Path("modules/whatsapp/flows_transporte.py").read_text(encoding="utf-8")

    assert 'sugerir_sucursales_correo_pedido(pedido, canal_origen="wa")' in texto
