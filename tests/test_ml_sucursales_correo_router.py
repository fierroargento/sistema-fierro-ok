from pathlib import Path


def test_sugerir_sucursales_delega_a_correo_si_transporte_es_correo():
    html = Path("app.py").read_text(encoding="utf-8")

    assert 'if "correo" in transporte_actual:' in html
    assert "sugerir_sucursales_correo_pedido" in html
    assert 'return sugerir_sucursales_correo_pedido(pedido)' in html
    assert 'armar_mensaje_sucursales(sucs, transporte="Vía Cargo")' in html
