from pathlib import Path
import re


def _app():
    return Path("app.py").read_text(encoding="utf-8")


def _bloque_funcion(texto, nombre, siguiente):
    return texto.split(f"def {nombre}(", 1)[1].split(f"def {siguiente}(", 1)[0]


def _consulta_global_pedido(texto):
    return re.search(r"(?<![A-Za-z])Pedido\.query", texto) is not None


def test_helpers_exigen_membresia_y_ocultan_pedido_ajeno():
    app = _app()
    consulta = _bloque_funcion(
        app, "consulta_pedidos_tenant_actual", "pedido_tenant_actual_o_404"
    )
    detalle = _bloque_funcion(app, "pedido_tenant_actual_o_404", "rol_actual")
    assert "membresia_actual()" in consulta
    assert "consulta_pedidos_tenant(" in consulta
    assert "membresia.organizacion_id" in consulta
    assert "unidad_negocio_actual_o_403" in consulta
    assert "unidad_negocio_id=unidad.id" in consulta
    assert "obtener_pedido_tenant(" in detalle
    assert "unidad_negocio_id=unidad.id" in detalle
    assert "abort(404)" in detalle
    assert not _consulta_global_pedido(consulta + detalle)


def test_inicio_y_preparacion_particionan_antes_de_filtrar_estado():
    app = _app()
    inicio = _bloque_funcion(app, "inicio", "pedidos_preparacion")
    preparacion = _bloque_funcion(app, "pedidos_preparacion", "despacho_mobile")
    assert inicio.count("consulta_pedidos_tenant_actual()") == 3
    assert not _consulta_global_pedido(inicio)
    assert "consulta_pedidos_tenant_actual()" in preparacion
    assert not _consulta_global_pedido(preparacion)


def test_despacho_historico_y_detalle_usan_frontera_tenant():
    app = _app()
    despacho = _bloque_funcion(app, "despacho_mobile", "ml_api_contexto_webhook")
    historico = _bloque_funcion(app, "historico", "productos")
    detalle = _bloque_funcion(app, "detalle_pedido", "revisar_agregado_mobile")
    assert "consulta_pedidos_tenant_actual()" in despacho
    assert not _consulta_global_pedido(despacho)
    assert "consulta_pedidos_tenant_actual()" in historico
    assert not _consulta_global_pedido(historico)
    assert "pedido_tenant_actual_o_404(id)" in detalle
    assert "Pedido.query.get_or_404(id)" not in detalle


def test_lote_no_modifica_rutas_de_integracion_o_automatizacion():
    app = _app()
    helper = _bloque_funcion(
        app, "consulta_pedidos_tenant_actual", "rol_actual"
    )
    for prohibido in (
        "ml_sync", "tn_sync", "webhook", "requests", "access_token",
        "db.session.commit", "db.session.delete",
    ):
        assert prohibido not in helper


def test_servicio_central_sigue_sin_compatibilidad_global():
    servicio = Path("services/acceso_tenant_pedidos.py").read_text(encoding="utf-8")
    assert "Pedido.query.filter_by(organizacion_id=organizacion_id)" in servicio
    assert "Pedido.query.get" not in servicio
    assert "get_or_404" not in servicio
