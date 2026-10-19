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


def conteo_fraccionario():
    import json
    conteo=conteo_ejemplo();item=conteo.items[0].existencia.item_inventario
    item.tipo='insumo'
    item.atributos_json=json.dumps({'insumo_productivo_id':3,'unidad_medida':'kg',
        'precision_inventario':'milesimas','factor_inventario':1000})
    conteo.items[0].cantidad_esperada=2100
    return conteo


def test_plantilla_expone_gramos_y_conteo_sigue_entero():
    from services.inventario_conteos_excel import _leer_filas_xlsx
    conteo=conteo_fraccionario()
    filas=_leer_filas_xlsx(crear_plantilla_conteo(conteo))
    assert filas[0][-1]=='UNIDAD' and filas[1][-1]=='g'
    carga=crear_xlsx_conteo((filas[0],('PP6040H','Taller',2100,2000,'','g')))
    sesion=Sesion()
    importar_conteo_excel(conteo,archivo_xlsx(carga),db_session=sesion)
    assert conteo.items[0].cantidad_contada==2000 and conteo.items[0].diferencia==-100
    assert sesion.commits==1


@pytest.mark.parametrize('unidad',[None,'kg'])
def test_conteo_rechaza_unidad_ausente_o_distinta_sin_guardar(unidad):
    conteo=conteo_fraccionario();sesion=Sesion()
    encabezado=('SKU','UBICACION','ESPERADO','CONTADO','OBSERVACION')
    fila=('PP6040H','Taller',2100,2,'')
    if unidad:encabezado+=('UNIDAD',);fila+=(unidad,)
    carga=crear_xlsx_conteo((encabezado,fila))
    with pytest.raises(ValueError,match='unidad'):
        importar_conteo_excel(conteo,archivo_xlsx(carga),db_session=sesion)
    assert sesion.commits==0 and conteo.items[0].cantidad_contada is None
