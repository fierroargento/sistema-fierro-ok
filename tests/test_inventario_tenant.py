from pathlib import Path
from types import SimpleNamespace

from services.migraciones_saas import (
    organizacion_movimiento_legacy,
)


RAIZ = Path(__file__).resolve().parents[1]


def _leer(ruta):
    return (
        RAIZ
        .joinpath(ruta)
        .read_text(encoding="utf-8")
    )


def test_movimiento_declara_tenant_explicito():
    contenido = _leer(
        "models/movimiento_inventario.py"
    )

    assert (
        'db.ForeignKey("organizacion.id")'
        in contenido
    )
    assert (
        "organizacion_id = db.Column("
        in contenido
    )
    assert (
        'backref="movimientos_inventario"'
        in contenido
    )


def test_movimiento_nuevo_copia_tenant_existencia():
    contenido = _leer(
        "services/inventario_nucleo.py"
    )

    assert (
        "organizacion_id="
        "existencia.organizacion_id"
        in contenido
    )


def test_backfill_prioriza_tenant_existencia():
    movimiento = SimpleNamespace(
        existencia=SimpleNamespace(
            organizacion_id=27,
        )
    )

    assert (
        organizacion_movimiento_legacy(
            movimiento,
            1,
        )
        == 27
    )


def test_backfill_tiene_fallback_seguro():
    movimiento = SimpleNamespace(
        existencia=None
    )

    assert (
        organizacion_movimiento_legacy(
            movimiento,
            9,
        )
        == 9
    )


def test_migracion_es_aditiva():
    contenido = _leer(
        "services/migraciones_saas.py"
    )

    assert (
        "ALTER TABLE movimiento_inventario "
        in contenido
    )
    assert (
        "ADD COLUMN organizacion_id INTEGER"
        in contenido
    )
    assert "DROP TABLE" not in contenido
    assert "DROP COLUMN" not in contenido


def test_consultas_filtran_movimiento_por_tenant():
    contenido = _leer(
        "services/inventario_consultas.py"
    )

    assert (
        "MovimientoInventario.query"
        in contenido
    )
    assert (
        ".filter_by(\n"
        "            organizacion_id="
        "organizacion_id"
        in contenido
    )
    assert (
        ".join(ExistenciaSucursal)"
        not in contenido
    )


def test_productos_salen_del_catalogo_del_tenant():
    contenido = _leer(
        "services/inventario_consultas.py"
    )

    assert (
        "Catalogo.organizacion_id"
        in contenido
    )
    assert "productos_por_id" in contenido

    # Evita una consulta global directa a Producto.
    # CatalogoProducto.query contiene esa subcadena,
    # por eso se verifica el comienzo real de la linea.
    assert (
        "\n        Producto.query"
        not in contenido
    )


def test_consultas_no_dependen_de_flask():
    contenido = _leer(
        "services/inventario_consultas.py"
    )

    assert "from flask" not in contenido
    assert "request." not in contenido
    assert "session." not in contenido


def test_bootstrap_ejecuta_migracion_inventario():
    contenido = _leer("app.py")

    assert (
        "asegurar_movimiento_inventario_tenant("
        in contenido
    )
    assert "MovimientoInventario=(" in contenido
