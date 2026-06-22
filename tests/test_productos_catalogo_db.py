from services.productos_catalogo_db import (
    aplicar_datos_producto_modelo,
    asegurar_columnas_producto_logistica,
    crear_producto_desde_catalogo,
    sincronizar_productos_desde_catalogo,
)


class ProductoFalso:
    def __init__(self, sku="", descripcion=""):
        self.sku = sku
        self.descripcion = descripcion


class QueryFalsa:
    def __init__(self):
        self.delete_called = False

    def delete(self):
        self.delete_called = True


class SessionFalsa:
    def __init__(self):
        self.query_obj = QueryFalsa()
        self.added = []
        self.executed = []
        self.commit_count = 0

    def query(self, modelo):
        return self.query_obj

    def add(self, obj):
        self.added.append(obj)

    def execute(self, sql):
        self.executed.append(sql)

    def commit(self):
        self.commit_count += 1


class DbFalsa:
    def __init__(self):
        self.engine = object()
        self.session = SessionFalsa()


def test_aplicar_datos_producto_modelo_setea_campos_logisticos():
    producto = ProductoFalso()

    aplicar_datos_producto_modelo(producto, {
        "sku": "PP6040H",
        "descripcion": "Parrilla plegable",
        "peso_gr": 3200,
        "alto_cm": 5,
        "ancho_cm": 42,
        "largo_cm": 36,
        "permite_correo": True,
        "permite_via_cargo": False,
        "requiere_revision_logistica": True,
        "observacion_logistica": "Revisar embalaje",
    })

    assert producto.sku == "PP6040H"
    assert producto.descripcion == "Parrilla plegable"
    assert producto.peso_gr == 3200
    assert producto.alto_cm == 5
    assert producto.ancho_cm == 42
    assert producto.largo_cm == 36
    assert producto.permite_correo is True
    assert producto.permite_via_cargo is False
    assert producto.requiere_revision_logistica is True
    assert producto.observacion_logistica == "Revisar embalaje"


def test_crear_producto_desde_catalogo_crea_modelo_con_datos():
    producto = crear_producto_desde_catalogo(ProductoFalso, {
        "sku": "KIT001",
        "descripcion": "Kit pala y atizador",
        "peso_gr": 900,
    })

    assert isinstance(producto, ProductoFalso)
    assert producto.sku == "KIT001"
    assert producto.descripcion == "Kit pala y atizador"
    assert producto.peso_gr == 900


def test_sincronizar_productos_desde_catalogo_reemplaza_catalogo():
    db = DbFalsa()

    cantidad = sincronizar_productos_desde_catalogo([
        {
            "sku": "PP6040H",
            "descripcion": "Parrilla plegable",
            "peso_gr": 3200,
        },
        {
            "sku": "KIT001",
            "descripcion": "Kit pala y atizador",
            "peso_gr": 900,
        },
    ], ProductoFalso, db)

    assert cantidad == 2
    assert db.session.query_obj.delete_called is True
    assert len(db.session.added) == 2
    assert db.session.added[0].sku == "PP6040H"
    assert db.session.added[1].sku == "KIT001"
    assert db.session.commit_count == 1


def test_asegurar_columnas_producto_logistica_agrega_solo_faltantes():
    db = DbFalsa()

    class InspectorFalso:
        def get_columns(self, tabla):
            assert tabla == "producto"
            return [
                {"name": "id"},
                {"name": "sku"},
                {"name": "descripcion"},
                {"name": "peso_gr"},
            ]

    def inspect_fn(engine):
        assert engine is db.engine
        return InspectorFalso()

    def text_fn(sql):
        return sql

    agregadas = asegurar_columnas_producto_logistica(db, inspect_fn, text_fn)

    assert "peso_gr" not in agregadas
    assert "alto_cm" in agregadas
    assert "permite_correo" in agregadas
    assert any("ALTER TABLE producto ADD COLUMN alto_cm FLOAT" == sql for sql in db.session.executed)
    assert db.session.commit_count == 1


def test_asegurar_columnas_producto_logistica_no_commitea_si_no_agrega():
    db = DbFalsa()

    class InspectorFalso:
        def get_columns(self, tabla):
            return [
                {"name": "id"},
                {"name": "sku"},
                {"name": "descripcion"},
                {"name": "peso_gr"},
                {"name": "alto_cm"},
                {"name": "ancho_cm"},
                {"name": "largo_cm"},
                {"name": "permite_correo"},
                {"name": "permite_via_cargo"},
                {"name": "requiere_revision_logistica"},
                {"name": "observacion_logistica"},
            ]

    agregadas = asegurar_columnas_producto_logistica(
        db,
        inspect_fn=lambda engine: InspectorFalso(),
        text_fn=lambda sql: sql,
    )

    assert agregadas == []
    assert db.session.executed == []
    assert db.session.commit_count == 0
