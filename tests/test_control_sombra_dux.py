from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.control_sombra_dux import (
    comparar_sombra_dux,
    construir_fotografia_fierro,
    leer_exportacion_dux,
)


def test_lee_csv_dux_con_formato_argentino():
    archivo = BytesIO("Código;Producto;Existencia;Precio venta\npp6040;Parrilla;12;35.500,50\n".encode("utf-8"))
    filas = leer_exportacion_dux(archivo)
    assert filas == [{
        "sku": "PP6040",
        "nombre": "Parrilla",
        "stock": 12,
        "precio_centavos": 3550050,
    }]


def test_rechaza_sku_duplicado():
    archivo = BytesIO(b"sku;stock\nA;1\nA;2\n")
    with pytest.raises(ValueError, match="duplicado"):
        leer_exportacion_dux(archivo)


def test_fotografia_agrega_stock_de_todas_las_sucursales():
    items = [SimpleNamespace(id=1, sku="A", nombre="Producto A", catalogo_producto_id=7, activo=True)]
    existencias = [
        SimpleNamespace(item_inventario_id=1, stock_actual=4),
        SimpleNamespace(item_inventario_id=1, stock_actual=6),
    ]
    catalogos = [SimpleNamespace(id=7, precio_centavos=150000)]
    resultado = construir_fotografia_fierro(items=items, existencias=existencias, productos_catalogo=catalogos)
    assert resultado[0]["stock"] == 10
    assert resultado[0]["precio_centavos"] == 150000


def test_detecta_stock_precio_faltantes_e_inactivos():
    dux = [
        {"sku": "A", "nombre": "A", "stock": 8, "precio_centavos": 10000},
        {"sku": "B", "nombre": "B", "stock": 2, "precio_centavos": 20000},
    ]
    fierro = [
        {"sku": "A", "nombre": "A", "stock": 7, "precio_centavos": 11000, "activo": False},
        {"sku": "C", "nombre": "C", "stock": 1, "precio_centavos": 30000, "activo": True},
    ]
    resultado = comparar_sombra_dux(organizacion_id=4, dux=dux, fierro=fierro)
    por_sku = {fila["sku"]: fila for fila in resultado["detalles"]}
    assert por_sku["A"]["diferencias"] == ["stock", "precio", "inactivo_fierro"]
    assert por_sku["B"]["diferencias"] == ["falta_fierro"]
    assert por_sku["C"]["diferencias"] == ["solo_fierro"]
    assert resultado["listo_para_reemplazo"] is False
    assert resultado["conexiones_externas"] == 0
    assert resultado["publicaciones"] == 0


def test_control_identico_queda_listo_y_con_huella_reproducible():
    dux = [{"sku": "A", "nombre": "A", "stock": 5, "precio_centavos": 10000}]
    fierro = [{"sku": "A", "nombre": "A", "stock": 5, "precio_centavos": 10000, "activo": True}]
    uno = comparar_sombra_dux(organizacion_id=1, dux=dux, fierro=fierro)
    dos = comparar_sombra_dux(organizacion_id=1, dux=dux, fierro=fierro)
    assert uno["listo_para_reemplazo"] is True
    assert uno["huella_sha256"] == dos["huella_sha256"]


def test_servicio_no_tiene_red_persistencia_ni_publicacion():
    fuente = Path("services/control_sombra_dux.py").read_text(encoding="utf-8-sig").lower()
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "mercadolibre", "tiendanube", "cloudinary"):
        assert prohibido not in fuente


def test_ruta_es_tenant_y_solo_procesa_archivo_en_memoria():
    fuente = Path("modules/admin/inventario/routes.py").read_text(encoding="utf-8-sig")
    bloque = fuente.split("def control_sombra_dux():", 1)[1].split("return blueprint", 1)[0]
    assert "resolver_acceso()" in bloque
    assert "organizacion.id" in bloque
    assert "db.session" not in bloque
    assert "registrar_auditoria" not in bloque
    plantilla = Path("templates/admin_control_sombra_dux.html").read_text(encoding="utf-8-sig")
    assert "No consulta DUX" in plantilla
    assert "no modifica stock o precios" in plantilla
