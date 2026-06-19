from pathlib import Path


def test_scheduler_tracking_auto_usa_correo_y_mercado_envios():
    texto = Path("modules/whatsapp/scheduler.py").read_text(encoding="utf-8")

    assert "Tracking automático habilitado para Correo Argentino y Mercado Envíos" in texto
    assert "consultar_correo_formulario" in texto
    assert "es_mercado_envios" in texto
    assert "es_correo_tracking" in texto
    assert 'transporte = "Correo Argentino"' in texto
    assert 'url_para_registro = url or "micorreo"' in texto
    assert "Tracking automático Andreani desactivado" in texto
    assert "Tracking automático Vía Cargo desactivado" in texto


def test_scheduler_tracking_auto_no_exige_url_para_correo():
    texto = Path("modules/whatsapp/scheduler.py").read_text(encoding="utf-8")

    bloque_correo = texto.split("if es_correo_tracking:", 1)[1].split("else:", 1)[0]

    assert "consultar_correo_formulario" in bloque_correo
    assert "if not url" not in bloque_correo
    assert "mercado_envios=" in bloque_correo
