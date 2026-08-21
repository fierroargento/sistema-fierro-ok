from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def test_modelo_es_tenant_idempotente_y_no_ejecutable():
    modelo = _leer("models/inventario_pedidos.py")
    bloque = modelo.split("class PropuestaPublicacionInventario", 1)[1]
    assert '__tablename__ = "propuesta_publicacion_inventario"' in bloque
    assert '"organizacion_id", "clave_idempotencia"' in bloque
    assert 'default="preparada_sin_ejecucion"' in bloque
    assert "puede_ejecutar = db.Column" in bloque
    assert "default=False" in bloque


def test_cola_se_registra_y_consulta_por_tenant():
    app = _leer("app.py")
    bootstrap = _leer("services/bootstrap_modulos_web.py")
    consultas = _leer("services/inventario_consultas.py")
    assert '"PropuestaPublicacionInventario"' in app
    assert '"PropuestaPublicacionInventario"' in bootstrap
    assert 'modelos["PropuestaPublicacionInventario"]' in consultas
    assert "PropuestaPublicacion.query.filter_by(" in consultas
    assert "organizacion_id=organizacion_id" in consultas


def test_panel_declara_cola_desconectada_y_vacia():
    panel = _leer("templates/admin_inventario.html")
    assert "Cola de propuestas desconectada" in panel
    assert "No tiene adaptadores de salida ni permiso de ejecución" in panel
    assert "propuestas_publicacion_inventario" in panel
    assert "Ejecución: bloqueada" in panel


def test_bloque_no_importa_clientes_externos_ni_mueve_stock():
    archivos = (
        _leer("models/inventario_pedidos.py"),
        _leer("services/inventario_consultas.py"),
    )
    for contenido in archivos:
        assert "requests" not in contenido
        assert "ml_api" not in contenido
        assert "tn_api" not in contenido
        assert "MovimientoInventario(" not in contenido
