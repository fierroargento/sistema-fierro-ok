from pathlib import Path


def test_detalle_pedido_tiene_boton_gestion_correo_sin_resumen_costos():
    html = Path("templates/detalle_pedido.html").read_text(encoding="utf-8")

    assert "Gestionar envío Correo" in html
    assert 'rol_actual in ["admin", "carga", "despacho"]' in html
    assert 'url_for(\'editar_pedido\', id=pedido.id, paso=3)' in html
    assert "correo-resumen-operativo" not in html
    assert "Costo interno elegido" not in html
