from pathlib import Path


def test_simulacion_inventario_obtiene_pedido_dentro_del_tenant():
    texto = Path("services/inventario_pedidos.py").read_text(encoding="utf-8")
    inicio = texto.index("def simular_evento_pedido(")
    bloque = texto[inicio:]
    assert "obtener_pedido_tenant(" in bloque
    assert "organizacion_id = int(organizacion.id)" in bloque
    assert "Pedido.query.get" not in bloque


def test_cambio_es_preparatorio_y_no_invoca_canales():
    texto = Path("services/inventario_pedidos.py").read_text(encoding="utf-8").lower()
    inicio = texto.index("def simular_evento_pedido(")
    bloque = texto[inicio:]
    for prohibido in ("requests", "oauth", "access_token", "webhook", "mercadolibre"):
        assert prohibido not in bloque
