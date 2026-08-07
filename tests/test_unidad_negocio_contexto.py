from pathlib import Path


def test_panel_declara_selector_global_de_unidad():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    comercial = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    costos = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert '"/admin/comercial/unidad"' in rutas
    assert "session[\"unidad_negocio_id\"]" in rutas
    assert "Unidad administrativa" in comercial
    assert "Unidad administrativa" in costos


def test_consultas_comerciales_exigen_unidad():
    consultas = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    fuentes = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    assert "Catalogo.unidad_negocio_id == unidad_negocio_id" in consultas
    assert "unidad_negocio_id=unidad_negocio_id" in consultas
    assert "Catalogo.unidad_negocio_id == unidad_negocio_id" in fuentes
    assert "unidad_negocio_id.is_(None)" in fuentes


def test_mutaciones_rechazan_cruce_de_unidades():
    comercial = Path("services/comercial_admin.py").read_text(encoding="utf-8")
    catalogos = Path("services/catalogos_admin_comercial.py").read_text(encoding="utf-8")
    fuentes = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    assert "unidad_activa.id" in comercial
    assert "unidad_activa.id" in catalogos
    assert "unidad activa" in fuentes


def test_contexto_no_toca_operacion_logistica():
    servicio = Path("services/unidad_negocio_contexto.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    for prohibido in ("Pedido", "Despacho", "MercadoLibre", "TiendaNube", "OAuth"):
        assert prohibido not in servicio
    assert "/despacho" not in rutas


def test_lotes_y_exportaciones_quedan_en_unidad_activa():
    modelo = Path("models/importacion_masiva_costo.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    assert "unidad_negocio_id" in modelo
    assert rutas.count("unidad_negocio_id=unidad_activa.id") >= 8
    assert "asegurar_unidad_importacion_costos" in migraciones
