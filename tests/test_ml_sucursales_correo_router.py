from pathlib import Path


def test_sugerir_sucursales_delega_segun_transporte():
    app = Path("app.py").read_text(encoding="utf-8-sig")

    assert 'if "correo" in transporte_actual:' in app
    assert (
        "preparar_oferta_sucursales_correo_pedido"
        in app
    )
    assert "resultado_correo = (" in app
    assert 'canal_origen="ml"' in app
    assert "return resultado_correo.mensaje" in app

    assert "armar_sugerencia_via_cargo_pedido" in app
    assert (
        "resultado_via_cargo = "
        "armar_sugerencia_via_cargo_pedido("
    ) in app

    assert (
        'armar_mensaje_sucursales(sucs, transporte="Vía Cargo")'
        not in app
    )
