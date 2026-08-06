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
from services.listas_precios import (
    activar_item_lista,
    activar_politica_lista,
    crear_item_lista,
    crear_lista_precio,
    crear_politica_lista,
)


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

        organizacion = Organizacion(nombre="Grupo", slug="grupo-runtime-lista")
        producto = Producto(sku="LISTA-1", descripcion="Producto lista")
        db.session.add_all([organizacion, producto])
        db.session.flush()
        unidad = UnidadNegocio(
            organizacion_id=organizacion.id, nombre="Fierro", codigo="fierro-l"
        )
        db.session.add(unidad)
        db.session.flush()
        catalogo = Catalogo(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad.id,
            codigo="catalogo-l", nombre="Catalogo", moneda="ARS",
        )
        db.session.add(catalogo)
        db.session.flush()
        inclusion = CatalogoProducto(
            catalogo_id=catalogo.id, producto_id=producto.id,
            sku_comercial="LISTA-1", nombre_comercial="Producto lista",
            precio_centavos=0,
        )
        costo = CostoProductoVersion(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad.id,
            producto_id=producto.id, moneda="ARS", tipo="calculado",
            numero_version=1, costo_total_centavos=10000,
            estado="vigente", vigente=True,
        )
        db.session.add_all([inclusion, costo])
        db.session.commit()

        lista = crear_lista_precio(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad.id,
            codigo="mostrador", nombre="Mostrador", tipo="mostrador",
            Organizacion=Organizacion, UnidadNegocio=UnidadNegocio,
            ListaPrecio=ListaPrecio, db_session=db.session,
        )
        politica_uno = crear_politica_lista(
            lista, comision_pct=10, margen_objetivo_pct=20,
            PoliticaComercialLista=PoliticaComercialLista,
            db_session=db.session,
        )
        activar_politica_lista(
            politica_uno, PoliticaComercialLista=PoliticaComercialLista,
            db_session=db.session,
        )
        item_uno = crear_item_lista(
            lista=lista, catalogo_producto=inclusion,
            costo_version=costo, politica=politica_uno,
            impuesto_pct=21, ListaPrecioItem=ListaPrecioItem,
            db_session=db.session,
        )
        activar_item_lista(
            item_uno, ListaPrecioItem=ListaPrecioItem, db_session=db.session,
        )
        politica_dos = crear_politica_lista(
            lista, comision_pct=12, margen_objetivo_pct=20,
            PoliticaComercialLista=PoliticaComercialLista,
            db_session=db.session,
        )
        activar_politica_lista(
            politica_dos, PoliticaComercialLista=PoliticaComercialLista,
            db_session=db.session,
        )
        assert politica_uno.estado == "archivado"
        assert politica_dos.numero_version == 2
        assert item_uno.vigente is True
        db.drop_all()
    print("Runtime SQLite de listas OK")


if __name__ == "__main__":
    main()
