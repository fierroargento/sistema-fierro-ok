"""Verificación SQLite de la administración tenant de catálogos."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask

from extensions import db
from models.catalogo import Catalogo
from models.catalogo_producto import CatalogoProducto
from models.organizacion import Organizacion
from models.producto import Producto
from models.unidad_negocio import UnidadNegocio
from services.catalogos_admin_comercial import procesar_accion_catalogo_comercial


def main():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    modelos = {
        "Catalogo": Catalogo,
        "CatalogoProducto": CatalogoProducto,
        "Producto": Producto,
        "UnidadNegocio": UnidadNegocio,
    }
    with app.app_context():
        db.create_all()
        organizacion = Organizacion(nombre="Grupo runtime", slug="grupo-runtime-cat")
        otra = Organizacion(nombre="Otro runtime", slug="otro-runtime-cat")
        producto = Producto(sku="CAT-1", descripcion="Producto catálogo")
        db.session.add_all([organizacion, otra, producto])
        db.session.flush()
        unidad = UnidadNegocio(
            organizacion_id=organizacion.id, nombre="Fierro", codigo="fierro-cat"
        )
        db.session.add(unidad)
        db.session.commit()

        procesar_accion_catalogo_comercial(
            "crear_catalogo",
            {
                "unidad_catalogo_id": str(unidad.id),
                "codigo_catalogo": "fierro",
                "nombre_catalogo": "Catálogo Fierro",
                "moneda_catalogo": "ars",
            },
            organizacion=organizacion, unidad_activa=unidad,
            modelos=modelos, db_session=db.session,
        )
        catalogo = Catalogo.query.filter_by(codigo="fierro").one()
        assert catalogo.estado == "desactivado"
        assert catalogo.moneda == "ARS"

        procesar_accion_catalogo_comercial(
            "estado_catalogo",
            {"catalogo_id": str(catalogo.id), "estado": "prueba"},
            organizacion=organizacion, unidad_activa=unidad,
            modelos=modelos, db_session=db.session,
        )
        procesar_accion_catalogo_comercial(
            "agregar_producto_catalogo",
            {"catalogo_id": str(catalogo.id), "producto_id": str(producto.id)},
            organizacion=organizacion, unidad_activa=unidad,
            modelos=modelos, db_session=db.session,
        )
        inclusion = CatalogoProducto.query.one()
        assert catalogo.estado == "prueba"
        assert inclusion.sku_comercial == "CAT-1"
        assert inclusion.activo is False
        assert inclusion.disponible is False

        for accion in (
            "activar_producto_catalogo",
            "disponibilidad_producto_catalogo",
        ):
            procesar_accion_catalogo_comercial(
                accion,
                {"catalogo_producto_id": str(inclusion.id)},
                organizacion=organizacion, unidad_activa=unidad,
                modelos=modelos, db_session=db.session,
            )
        assert inclusion.activo is True
        assert inclusion.disponible is True

        try:
            procesar_accion_catalogo_comercial(
                "estado_catalogo",
                {"catalogo_id": str(catalogo.id), "estado": "activo"},
                organizacion=otra, unidad_activa=unidad,
                modelos=modelos, db_session=db.session,
            )
        except ValueError as error:
            assert "no pertenece" in str(error)
        else:
            raise AssertionError("Se permitió modificar un catálogo de otro tenant")

        db.drop_all()
    print("Runtime SQLite de catalogos comerciales OK")


if __name__ == "__main__":
    main()
