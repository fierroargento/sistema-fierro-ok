from io import BytesIO
from pathlib import Path

from services.importacion_productos_costeo import (
    leer_archivo,
    sugerir_mapeo,
    validar_mapeo,
)


class Archivo(BytesIO):
    filename = "productos.csv"


def test_lee_csv_y_sugiere_campos():
    archivo = Archivo(
        "SKU,TIPO,UNIDAD,OTRA\nPP6040H,produccion,Fierro,x\n".encode("utf-8")
    )
    lectura = leer_archivo(archivo)
    assert lectura["encabezados"] == ["SKU", "TIPO", "UNIDAD", "OTRA"]
    assert lectura["filas"][0]["numero"] == 2
    assert sugerir_mapeo(lectura["encabezados"]) == {
        "0": "sku", "1": "tipo", "2": "unidad", "3": "",
    }


def test_mapeo_exige_sku_y_tipo():
    try:
        validar_mapeo({"0": "sku"})
    except ValueError as error:
        assert "Tipo de producto" in str(error)
    else:
        raise AssertionError("Se acepto un mapeo incompleto.")


def test_interfaz_tiene_flujo_y_exportaciones():
    template = Path("templates/admin_importacion_productos_costeo.html").read_text(
        encoding="utf-8"
    )
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "1 · Archivo" in template
    assert "2 · Columnas" in template
    assert "3 · Vista previa" in template
    assert "Confirmar importación" in template
    assert "Descargar plantilla Excel" in template
    assert "Exportar Excel" in template
    assert "Exportar PDF" in template
    assert "seleccionar-columnas" in template
    assert "data-map-check" in template
    assert 'name="modo"' in template
    assert "Seleccionar todo" in Path(
        "static/admin_importacion_costos.js"
    ).read_text(encoding="utf-8")
    assert "plantilla_productos_costeo" in rutas
    assert "exportar_productos_costeo" in rutas


def test_modelo_lote_no_esta_en_app_como_logica():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "from models.importacion_masiva_costo import ImportacionMasivaCosto" in app
    assert "services.importacion_productos_costeo import" not in app


def test_motor_permanece_aislado_de_canales():
    contenido = Path("services/importacion_productos_costeo.py").read_text(
        encoding="utf-8"
    )
    for prohibido in ("MercadoLibre", "TiendaNube", "Pedido", "Webhook"):
        assert prohibido not in contenido
