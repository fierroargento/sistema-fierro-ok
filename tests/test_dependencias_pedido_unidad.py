from pathlib import Path


def _fuente(ruta):
    return Path(ruta).read_text(encoding="utf-8-sig")


def _funcion_app(nombre):
    bloque = _fuente("app.py").split(f"def {nombre}(", 1)[1]
    return bloque.split("\n@app.route", 1)[0]


def test_detalle_lee_notas_y_agregados_solo_del_pedido_protegido():
    bloque = _funcion_app("detalle_pedido")
    assert "pedido = pedido_tenant_actual_o_404(id)" in bloque
    assert "NotaPedido.query.filter_by(pedido_id=pedido.id)" in bloque
    assert ".filter_by(pedido_id=pedido.id)" in bloque
    assert "PedidoAgregadoAPB.query" in bloque


def test_notas_directas_encadenan_identificador_y_pedido_protegido():
    for nombre in ("editar_nota_pedido", "eliminar_nota_pedido"):
        bloque = _funcion_app(nombre)
        assert "pedido = pedido_tenant_actual_o_404(id)" in bloque
        assert "id=nota_id, pedido_id=pedido.id" in bloque


def test_items_y_agregados_se_crean_con_el_pedido_protegido():
    bloque = _funcion_app("agregar_item_pedido")
    assert "pedido = pedido_tenant_actual_o_404(id)" in bloque
    assert "PedidoAgregadoAPB(" in bloque
    assert "pedido_id=pedido.id" in bloque
    assert "PedidoItem(" in bloque


def test_servicios_conversacionales_no_aceptan_pedido_id_suelto():
    conversacional = _fuente("services/conversacional.py")
    eventos = _fuente("services/eventos_operativos.py")
    assert "def obtener_estado_conversacional_service(\n    pedido," in conversacional
    assert "pedido_id=pedido.id" in conversacional
    assert "pedido_id=getattr(pedido, \"id\", None)" in eventos
    assert "pedido_id=" not in eventos.split("def registrar_evento_operativo_service(", 1)[1].split("):", 1)[0]
