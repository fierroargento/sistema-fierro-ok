from pathlib import Path


def test_certificacion_es_diagnostica_y_bloquea_integraciones():
    servicio = Path("services/certificacion_productos_tenant.py").read_text(
        encoding="utf-8"
    )
    assert "def certificar_productos_tenant(" in servicio
    assert '"integraciones_habilitables": False' in servicio
    assert "db.session.add" not in servicio
    assert ".commit(" not in servicio
    assert ".delete(" not in servicio


def test_costos_e_inventario_exigen_producto_del_tenant():
    costos = Path("services/costos_productos.py").read_text(encoding="utf-8")
    inventario = Path("services/inventario_admin.py").read_text(encoding="utf-8")
    assert "producto.organizacion_id" in costos
    assert '"El producto",' in inventario


def test_panel_muestra_resultado_sin_habilitar_canales():
    plantilla = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    consultas = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    assert "Certificación del maestro de productos" in plantilla
    assert "Integraciones externas bloqueadas" in plantilla
    assert "certificar_productos_tenant(" in consultas
