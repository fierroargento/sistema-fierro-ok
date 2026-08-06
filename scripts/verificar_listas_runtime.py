"""Verificacion real SQLite de modelos comerciales."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask
from sqlalchemy import inspect

from extensions import db
from models.catalogo import Catalogo
from models.catalogo_producto import CatalogoProducto
from models.costo_producto_detalle import CostoProductoDetalle
from models.costo_producto_version import CostoProductoVersion
from models.lista_precio import ListaPrecio
from models.lista_precio_item import ListaPrecioItem
from models.organizacion import Organizacion
from models.politica_comercial_lista import PoliticaComercialLista
from models.producto import Producto
from models.unidad_negocio import UnidadNegocio
from models.usuario_sistema import UsuarioSistema


def main():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        tablas = set(inspector.get_table_names())
        esperadas = {
            "lista_precio", "politica_comercial_lista", "lista_precio_item",
        }
        assert esperadas <= tablas
        indices_politica = {
            item["name"] for item in inspector.get_indexes(
                "politica_comercial_lista"
            )
        }
        indices_item = {
            item["name"] for item in inspector.get_indexes("lista_precio_item")
        }
        assert "uq_politica_lista_vigente" in indices_politica
        assert "uq_lista_item_vigente" in indices_item
        db.drop_all()
    print("Runtime SQLite de listas OK")


if __name__ == "__main__":
    main()
