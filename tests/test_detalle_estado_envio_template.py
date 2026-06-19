from pathlib import Path


def test_estado_envio_aparece_antes_de_seguimiento_en_venta():
    html = Path("templates/detalle_pedido.html").read_text(encoding="utf-8")

    pos_estado = html.index("<strong>Estado de Envío:</strong>")
    pos_seguimiento = html.index("<strong>Seguimiento:</strong>")

    assert pos_estado < pos_seguimiento
    assert "correo-resumen-operativo" not in html
    assert "Costo interno elegido" not in html
