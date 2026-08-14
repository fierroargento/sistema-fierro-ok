from io import BytesIO
from types import SimpleNamespace

import pytest
from services.inventario_conteos_excel import (
    crear_plantilla_conteo,
    crear_xlsx_conteo,
    importar_conteo_excel,
)


class Sesion:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def conteo_ejemplo():
    existencia = SimpleNamespace(
        item_inventario=SimpleNamespace(sku="PP6040H"),
        producto=None,
    )
    item = SimpleNamespace(
        existencia=existencia,
        cantidad_esperada=2,
        cantidad_contada=None,
        diferencia=None,
        observacion=None,
    )
    return SimpleNamespace(
        estado="abierto",
        sucursal=SimpleNamespace(nombre="Taller"),
        items=[item],
    )


def archivo_xlsx(datos, nombre="conteo.xlsx"):
    datos.seek(0)
    datos.filename = nombre
    return datos


def test_plantilla_e_importacion_preparan_vista_previa_sin_stock():
    conteo = conteo_ejemplo()
    salida = crear_plantilla_conteo(conteo)
    assert salida.read(2) == b"PK"
    carga = crear_xlsx_conteo((
        ("SKU", "UBICACION", "ESPERADO", "CONTADO", "OBSERVACION"),
        ("PP6040H", "Taller", 2, 5, "Conteo inicial"),
    ))
    sesion = Sesion()

    filas = importar_conteo_excel(
        conteo,
        archivo_xlsx(carga),
        db_session=sesion,
    )

    assert filas == 1
    assert conteo.estado == "contado"
    assert conteo.items[0].cantidad_contada == 5
    assert conteo.items[0].diferencia == 3
    assert conteo.items[0].observacion == "Conteo inicial"
    assert sesion.commits == 1


def test_importacion_rechaza_formato_y_filas_incompletas():
    conteo = conteo_ejemplo()
    with pytest.raises(ValueError, match="formato XLSX"):
        importar_conteo_excel(
            conteo,
            archivo_xlsx(BytesIO(b"texto"), "conteo.csv"),
            db_session=Sesion(),
        )

    carga = crear_xlsx_conteo((
        ("SKU", "UBICACION", "ESPERADO", "CONTADO", "OBSERVACION"),
        ("PP6040H", "Taller", 2, None, ""),
    ))
    with pytest.raises(ValueError, match="cantidad entera"):
        importar_conteo_excel(
            conteo,
            archivo_xlsx(carga),
            db_session=Sesion(),
        )
