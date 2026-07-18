from pathlib import Path


def test_selector_correo_delega_canal_origen_al_servicio_central():
    selector = Path(
        "modules/transportes/selector.py"
    ).read_text(encoding="utf-8")

    assert (
        'def sugerir_sucursales_correo_pedido('
        'pedido, canal_origen="ml"):'
    ) in selector

    assert (
        'canal_origen = str('
        'canal_origen or "ml").strip().lower()'
    ) in selector

    assert (
        "aplicar_oferta_sucursales_correo_al_pedido"
        in selector
    )

    assert "canal_origen=canal_origen" in selector

    assert (
        'pedido.wa_estado = "falta_elegir_transporte"'
        not in selector
    )


def test_whatsapp_pasa_canal_origen_wa_al_selector_correo():
    texto = Path("modules/whatsapp/flows_transporte.py").read_text(encoding="utf-8")

    assert (
        "preparar_oferta_sucursales_correo_pedido"
        in texto
    )
    assert 'canal_origen="wa"' in texto
    assert "if resultado_suc.ok:" in texto
    assert "db.session.commit()" in texto
    assert "db.session.rollback()" in texto
    assert "resultado_suc.mensaje" in texto
    assert (
        'sugerir_sucursales_correo_pedido('
        'pedido, canal_origen="wa")'
        not in texto
    )
