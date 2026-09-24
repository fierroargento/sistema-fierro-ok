import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import zipfile

from services.catalogo_ficha_integral import prevalidar_imagenes
from services.importacion_fuentes_costeo import DEFINICIONES, sugerir_mapeo_fuente
from services.importacion_inclusiones_catalogo import sugerir_mapeo_inclusiones
from services.importacion_productos_costeo import sugerir_mapeo
from services.importacion_proveedores_compra import sugerir_mapeo_proveedores
from services.paquete_datos_uat import ARCHIVOS_CSV, construir_paquete_uat


class Archivo:
    def __init__(self, contenido, nombre):
        self.stream = BytesIO(contenido)
        self.filename = nombre

    def read(self, *args):
        return self.stream.read(*args)


def _encabezados(paquete, nombre):
    texto = paquete.read(nombre).decode("utf-8-sig")
    return next(csv.reader(StringIO(texto)))


def test_paquete_contiene_secuencia_completa_y_firmada():
    with zipfile.ZipFile(construir_paquete_uat()) as paquete:
        nombres = set(paquete.namelist())
        assert set(ARCHIVOS_CSV) <= nombres
        assert {"09_imagen_producto_uat.png", "LEEME_PRIMERO.txt", "MANIFIESTO.json"} <= nombres
        manifiesto = json.loads(paquete.read("MANIFIESTO.json"))
        assert manifiesto["datos_reales"] is False
        assert manifiesto["autoriza_activacion"] is False
        assert manifiesto["autoriza_conexiones"] is False
        assert len(manifiesto["archivos"]) == 10


def test_paquete_es_reproducible_byte_a_byte():
    assert construir_paquete_uat().getvalue() == construir_paquete_uat().getvalue()


def test_encabezados_son_reconocidos_por_importadores_reales():
    with zipfile.ZipFile(construir_paquete_uat()) as paquete:
        inclusion = _encabezados(paquete, "01_inclusiones_catalogo.csv")
        assert set(sugerir_mapeo_inclusiones(inclusion).values()) >= {
            "catalogo_codigo", "sku", "descripcion",
        }
        clasificacion = _encabezados(paquete, "02_clasificacion_productos.csv")
        assert set(sugerir_mapeo(clasificacion).values()) >= {"sku", "tipo"}
        for nombre, tipo in (
            ("03_insumos.csv", "insumos"),
            ("04_empleados.csv", "empleados"),
            ("05_maquinas.csv", "maquinas"),
            ("06_costos_fijos.csv", "costos-fijos"),
            ("07_fichas_tecnicas.csv", "fichas"),
        ):
            mapeo = sugerir_mapeo_fuente(tipo, _encabezados(paquete, nombre))
            obligatorios = {
                campo for campo, (_etiqueta, obligatorio)
                in DEFINICIONES[tipo]["campos"].items() if obligatorio
            }
            assert obligatorios <= set(mapeo.values())
        proveedores = _encabezados(paquete, "08_proveedores.csv")
        assert set(sugerir_mapeo_proveedores(proveedores).values()) >= {
            "codigo", "razon_social", "cuit",
        }


def test_imagen_sintetica_es_valida_y_no_es_catalogo_real():
    with zipfile.ZipFile(construir_paquete_uat()) as paquete:
        contenido = paquete.read("09_imagen_producto_uat.png")
    _archivos, resumen = prevalidar_imagenes([
        Archivo(contenido, "09_imagen_producto_uat.png")
    ])
    assert resumen[0]["ancho"] == 1200
    assert resumen[0]["alto"] == 1200


def test_generador_declara_frontera_offline_y_salida_explicita():
    servicio = Path("services/paquete_datos_uat.py").read_text(encoding="utf-8")
    script = Path("scripts/generar_paquete_datos_uat.py").read_text(encoding="utf-8")
    for prohibido in ("requests.", "urlopen", "db.session", "DATABASE_URL"):
        assert prohibido not in servicio
    assert 'parser.add_argument("--salida", required=True)' in script
    assert "--sobrescribir" in script
