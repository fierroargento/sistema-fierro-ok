from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def test_modelo_aisla_producto_e_identidad_externa_por_cuenta():
    modelo = _leer("models/mapeo_publicacion_canal.py")
    assert 'class MapeoPublicacionCanal(db.Model)' in modelo
    assert '"organizacion_id", "vinculo_canal_comercial_id"' in modelo
    assert '"catalogo_producto_id"' in modelo
    assert '"publicacion_externa_id", "variante_externa_id"' in modelo
    assert "uq_mapeo_publicacion_cuenta_producto" in modelo
    assert "uq_mapeo_publicacion_cuenta_identidad_externa" in modelo


def test_mapeo_nace_desconectado_y_sin_permiso_de_sincronizar():
    modelo = _leer("models/mapeo_publicacion_canal.py")
    assert 'default="preparado_sin_conexion"' in modelo
    assert "identidad_verificada = db.Column" in modelo
    assert "permite_sincronizar = db.Column" in modelo
    assert modelo.count("default=False") >= 2


def test_modelo_se_registra_y_consulta_por_tenant():
    app = _leer("app.py")
    bootstrap = _leer("services/bootstrap_modulos_web.py")
    consultas = _leer("services/inventario_consultas.py")
    assert '"MapeoPublicacionCanal": MapeoPublicacionCanal' in app
    assert '"MapeoPublicacionCanal"' in bootstrap
    assert 'modelos["MapeoPublicacionCanal"]' in consultas
    assert "MapeoPublicacionCanal.query" in consultas
    assert "filter_by(organizacion_id=organizacion_id)" in consultas


def test_panel_declara_registro_vacio_y_desconectado():
    panel = _leer("templates/admin_inventario.html")
    assert "Identidad de publicaciones por cuenta" in panel
    assert "Registro estructural desconectado" in panel
    assert "mapeos_publicaciones" in panel
    assert "Sincronización: bloqueada" in panel
    assert "No se consultaron datos externos" in panel


def test_bloque_no_incluye_clientes_externos():
    for ruta in (
        "models/mapeo_publicacion_canal.py",
        "services/inventario_consultas.py",
    ):
        contenido = _leer(ruta)
        assert "requests" not in contenido
        assert "ml_api" not in contenido
        assert "tn_api" not in contenido
