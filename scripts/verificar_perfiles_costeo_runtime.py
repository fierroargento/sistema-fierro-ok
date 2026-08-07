"""Runtime SQLite de perfiles Simple, Produccion y Combo."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask
from sqlalchemy import inspect

from extensions import db
from models.organizacion import Organizacion
from models.perfil_costeo_producto import ComboProductoComponente, PerfilCosteoProducto
from models.producto import Producto
from models.unidad_negocio import UnidadNegocio
from services.perfiles_costeo import agregar_componente_combo, crear_o_actualizar_perfil


def main():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        tablas = set(inspect(db.engine).get_table_names())
        assert {"perfil_costeo_producto", "combo_producto_componente"}.issubset(tablas)
        org = Organizacion(nombre="Grupo Fierro", slug="grupo-fierro-perfiles")
        simple = Producto(sku="FUNDA", descripcion="Funda")
        producido = Producto(sku="PP6040H", descripcion="Parrilla")
        combo_producto = Producto(sku="COMBO-1", descripcion="Parrilla con funda")
        db.session.add_all([org, simple, producido, combo_producto])
        db.session.flush()
        unidad = UnidadNegocio(
            organizacion_id=org.id, codigo="fierro-perfiles", nombre="Fierro",
        )
        db.session.add(unidad)
        db.session.commit()

        def perfil(producto, tipo):
            return crear_o_actualizar_perfil(
                organizacion_id=org.id, unidad_negocio_id=unidad.id,
                producto_id=producto.id, tipo=tipo,
                PerfilCosteoProducto=PerfilCosteoProducto,
                UnidadNegocio=UnidadNegocio, Producto=Producto,
                db_session=db.session,
            )

        perfil_simple = perfil(simple, "simple")
        perfil_producido = perfil(producido, "produccion")
        perfil_combo = perfil(combo_producto, "combo")
        agregar_componente_combo(
            perfil_combo, perfil_simple, cantidad="1",
            ComboProductoComponente=ComboProductoComponente,
            db_session=db.session,
        )
        agregar_componente_combo(
            perfil_combo, perfil_producido, cantidad="1",
            ComboProductoComponente=ComboProductoComponente,
            db_session=db.session,
        )
        assert len(perfil_combo.componentes_combo) == 2
        try:
            agregar_componente_combo(
                perfil_combo, perfil_combo, cantidad="1",
                ComboProductoComponente=ComboProductoComponente,
                db_session=db.session,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Se permitio anidar un combo.")
        db.session.remove()
        db.drop_all()
    print("Runtime SQLite de perfiles de costeo OK")


if __name__ == "__main__":
    main()
