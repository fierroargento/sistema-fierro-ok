from pathlib import Path


def _app():
    return Path("app.py").read_text(encoding="utf-8")


def _funcion(nombre):
    bloque = _app().split(f"def {nombre}(", 1)[1]
    return bloque.split("\n@app.route", 1)[0]


def test_archivos_e_impresion_resuelven_pedido_dentro_del_tenant():
    sin_id = _funcion("ver_archivo_pedido_sin_id_compat")
    por_id = _funcion("ver_archivo_pedido_compat")
    lanzar = _funcion("lanzar_impresion")
    imprimir = _funcion("imprimir_etiqueta")
    assert "consulta_pedidos_tenant_actual()" in sin_id
    assert "Pedido.query" not in sin_id
    assert "pedido_tenant_actual_o_404(pedido_id)" in por_id
    assert "pedido_tenant_actual_o_404(id)" in lanzar
    assert "pedido_tenant_actual_o_404(id)" in imprimir
    assert "Pedido.query.get_or_404" not in por_id + lanzar + imprimir


def test_revision_ediciones_y_agregado_exigen_pedido_tenant():
    for nombre in (
        "revisar_agregado_mobile",
        "admin_editar_pedido_completo",
        "editar_pedido",
        "agregar_item_pedido",
    ):
        bloque = _funcion(nombre)
        assert "pedido_tenant_actual_o_404(id)" in bloque, nombre
        assert "Pedido.query.get_or_404" not in bloque, nombre


def test_notas_exigen_pedido_tenant_y_relacion_con_el_pedido():
    agregar = _funcion("agregar_nota_pedido")
    editar = _funcion("editar_nota_pedido")
    eliminar = _funcion("eliminar_nota_pedido")
    assert "pedido_tenant_actual_o_404(id)" in agregar
    for bloque in (editar, eliminar):
        assert "pedido = pedido_tenant_actual_o_404(id)" in bloque
        assert "id=nota_id, pedido_id=pedido.id" in bloque
        assert "NotaPedido.query.get_or_404" not in bloque


def test_frontera_ocurre_antes_de_autorizacion_o_mutacion():
    for nombre in (
        "lanzar_impresion", "imprimir_etiqueta", "agregar_nota_pedido",
        "admin_editar_pedido_completo", "editar_pedido", "agregar_item_pedido",
    ):
        bloque = _funcion(nombre)
        frontera = bloque.index("pedido_tenant_actual_o_404")
        posiciones = [
            posicion for marcador in (
                "puede_", "db.session.commit", "db.session.add", "setattr("
            )
            if (posicion := bloque.find(marcador)) >= 0
        ]
        assert not posiciones or frontera < min(posiciones), nombre


def test_sincronizaciones_y_mensajeria_ya_exigen_tenant():
    for nombre in (
        "resync_ml_pedido", "sync_mensajes_ml_pedido_admin", "resync_tn_pedido",
        "enviar_mensaje_ml_acordas", "whatsapp_enviar_operador",
        "whatsapp_iniciar_chat_operador",
    ):
        bloque = _funcion(nombre)
        assert "pedido_tenant_actual_o_404(id)" in bloque, nombre
        assert "Pedido.query.get_or_404(id)" not in bloque, nombre
