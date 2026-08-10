from pathlib import Path


def test_edicion_cliente_web_es_modular_y_acotada():
    app = Path("app.py").read_text(encoding="utf-8")
    rutas = Path(
        "modules/pedidos/edicion_cliente_routes.py"
    ).read_text(encoding="utf-8")
    servicio = Path(
        "services/edicion_datos_cliente.py"
    ).read_text(encoding="utf-8")
    template = Path(
        "templates/editar_datos_cliente_etiqueta.html"
    ).read_text(encoding="utf-8")
    detalle = Path(
        "templates/detalle_pedido.html"
    ).read_text(encoding="utf-8")

    assert "def crear_blueprint_edicion_cliente(" in rutas
    assert "def aplicar_edicion_datos_cliente_para_etiqueta(" in servicio
    assert "def aplicar_edicion_datos_cliente_para_etiqueta(" not in app
    assert "from app import" not in rutas + servicio
    assert "canal" not in template
    assert 'name="id_venta"' not in template
    assert 'name="estado"' not in template
    assert 'name="items_texto"' not in template
    assert "pedidos_edicion_cliente.editar" in detalle


def test_carga_solo_ve_boton_antes_de_etiqueta_impresa():
    detalle = Path(
        "templates/detalle_pedido.html"
    ).read_text(encoding="utf-8")

    assert 'rol_actual in ["admin", "carga"]' in detalle
    assert "not pedido.fecha_etiqueta_impresa" in detalle
    assert 'pedido.estado in ["Cargando Pedido", "Etiqueta Lista"]' in detalle
