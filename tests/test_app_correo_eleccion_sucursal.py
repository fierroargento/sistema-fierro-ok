from pathlib import Path


def test_app_detectar_sucursal_rutea_correo_y_ofrecidas_correo():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "detectar_sucursal_correo_ofrecida" in texto
    assert 'if "correo" in transporte_actual:' in texto
    assert 'or getattr(pedido, "correo_sucursales_ofrecidas", None)' in texto
    assert 're.search(r"\\b([1-5])\\b", t)' in texto
