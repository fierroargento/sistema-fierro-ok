from pathlib import Path

from models.producto import Producto
from services import logistica_catalogo


def test_producto_expone_modelo_canonico():
    assert Producto.__tablename__ == "producto"

    columnas = {
        "id",
        "sku",
        "descripcion",
        "peso_gr",
        "alto_cm",
        "ancho_cm",
        "largo_cm",
        "permite_correo",
        "permite_via_cargo",
        "requiere_revision_logistica",
        "observacion_logistica",
    }

    assert columnas.issubset(set(Producto.__dict__))


def test_logistica_catalogo_usa_producto_canonico():
    assert logistica_catalogo.ProductoModel is Producto


def test_producto_no_depende_de_app():
    modelo = Path(
        "models/producto.py"
    ).read_text(encoding="utf-8")

    servicio = Path(
        "services/logistica_catalogo.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert "from app import Producto" not in servicio
    assert "class Producto" not in app
    assert "from models.producto import Producto" in app
    assert (
        "from models.producto import "
        "Producto as ProductoModel"
        in servicio
    )
