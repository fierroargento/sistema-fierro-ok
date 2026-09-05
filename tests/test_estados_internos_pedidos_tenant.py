from pathlib import Path


def _app():
    return Path("app.py").read_text(encoding="utf-8")


def _funcion(nombre):
    return _app().split(f"def {nombre}(", 1)[1].split("\n@app.route", 1)[0]


def test_seis_transiciones_internas_exigen_pedido_del_tenant():
    nombres = (
        "cerrar_pedido",
        "marcar_no_entregado",
        "gestionar_devolucion",
        "cerrar_reclamo_ml_devolucion",
        "revisar_reclamo",
        "confirmar_revision_agregado",
    )
    for nombre in nombres:
        bloque = _funcion(nombre)
        assert "pedido_tenant_actual_o_404(id)" in bloque, nombre
        assert "Pedido.query.get_or_404(id)" not in bloque, nombre


def test_frontera_precede_permisos_y_cualquier_mutacion():
    for nombre in (
        "cerrar_pedido", "marcar_no_entregado", "gestionar_devolucion",
        "cerrar_reclamo_ml_devolucion", "revisar_reclamo",
        "confirmar_revision_agregado",
    ):
        bloque = _funcion(nombre)
        frontera = bloque.index("pedido_tenant_actual_o_404(id)")
        posiciones = [
            posicion for marcador in (
                "puede_", "pedido.estado =", "db.session.commit",
                "resolver_agregado_pendiente(",
            )
            if (posicion := bloque.find(marcador)) >= 0
        ]
        assert not posiciones or frontera < min(posiciones), nombre


def test_acciones_con_efectos_externos_tambien_exigen_tenant():
    for nombre in (
        "confirmar_entrega", "confirmar_cierre_pedido", "avanzar_pedido",
        "devolver_pedido_a_ml",
    ):
        bloque = _funcion(nombre)
        assert "pedido_tenant_actual_o_404(id)" in bloque, nombre
        assert "Pedido.query.get_or_404(id)" not in bloque, nombre


def test_lote_no_agrega_transporte_a_las_transiciones_internas():
    for nombre in (
        "cerrar_pedido", "marcar_no_entregado", "gestionar_devolucion",
        "cerrar_reclamo_ml_devolucion", "revisar_reclamo",
    ):
        bloque = _funcion(nombre).lower()
        for prohibido in (
            "requests.", "access_token", "ml_sync", "tn_sync",
            "wa_enviar", "webhook",
        ):
            assert prohibido not in bloque, (nombre, prohibido)


def test_confirmar_revision_solo_delega_resolucion_interna():
    bloque = _funcion("confirmar_revision_agregado")
    assert "resolver_agregado_pendiente(" in bloque
    assert "wa_enviar" not in bloque
    assert "ml_sync" not in bloque
