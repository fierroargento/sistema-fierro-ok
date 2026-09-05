from pathlib import Path

def test_un_mismo_sku_puede_existir_en_dos_organizaciones():
    modelo = Path("models/producto.py").read_text(encoding="utf-8")
    assert '"organizacion_id",\n            "sku"' in modelo
    assert 'name="uq_producto_organizacion_sku"' in modelo
    assert "organizacion_id = db.Column(" in modelo


def test_migracion_conserva_productos_legacy_en_tenant_inicial():
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_base_datos.py").read_text(encoding="utf-8")
    assert "def asegurar_producto_tenant(" in migraciones
    assert "Producto.organizacion_id.is_(None)" in migraciones
    assert "producto.organizacion_id = organizacion_id_predeterminada" in migraciones
    assert "asegurar_producto_tenant(" in bootstrap


def test_consultas_visibles_filtran_producto_por_organizacion():
    estructura = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    comercial = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    assert "Producto.query\n        .filter_by" in estructura
    assert "Producto.query.filter_by(" in comercial
