from pathlib import Path


def test_detalle_muestra_boton_consultar_estado_tracking_externo():
    html = Path("templates/detalle_pedido.html").read_text(encoding="utf-8")

    assert "Consultar estado" in html
    assert "actualizar_tracking_externo_pedido" in html
    assert "puede_actualizar_tracking_externo(pedido)" in html
    assert 'method="POST"' in html
    assert "abrirTrackingConCopia" in html
