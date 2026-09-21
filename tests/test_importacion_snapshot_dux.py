import io,json
from pathlib import Path
import pytest
from services.importacion_snapshot_dux import convertir_exportaciones,exportar,plantilla_productos,plantilla_pedidos
def test_convierte_csv_punto_y_coma_y_normaliza():
 r=convertir_exportaciones(io.BytesIO("SKU;STOCK;PRECIO_CENTAVOS;ACTIVO\n abc ;5;125000;SI\n".encode()));assert r["productos"]==[{"sku":"ABC","stock":5,"precio_centavos":125000,"activo":True}]
def test_admite_coma_aliases_y_pedidos():
 p=io.BytesIO(b"CODIGO,STOCK,PRECIO,ACTIVO\nX,2,900,NO\n");o=io.BytesIO(b"ID_VENTA\nP-1\n");r=convertir_exportaciones(p,o);assert not r["productos"][0]["activo"] and r["pedidos_abiertos"]==[{"id_externo":"P-1"}]
def test_rechaza_sku_y_pedido_duplicados():
 with pytest.raises(ValueError,match="SKU duplicado"):convertir_exportaciones(io.BytesIO(b"SKU;STOCK;PRECIO\nX;1;2\nX;1;2\n"))
 with pytest.raises(ValueError,match="Pedido duplicado"):convertir_exportaciones(io.BytesIO(b"SKU;STOCK;PRECIO\nX;1;2\n"),io.BytesIO(b"PEDIDO\nA\nA\n"))
def test_rechaza_campos_numericos_invalidos():
 with pytest.raises(ValueError,match="STOCK invalido"):convertir_exportaciones(io.BytesIO(b"SKU;STOCK;PRECIO\nX;mal;2\n"))
def test_firma_reproducible_exportable_y_sin_impacto():
 contenido=b"SKU;STOCK;PRECIO\nX;1;2\n";a=convertir_exportaciones(io.BytesIO(contenido));b=convertir_exportaciones(io.BytesIO(contenido));assert a["huella_snapshot"]==b["huella_snapshot"]==json.load(exportar(a))["huella_snapshot"] and not any(a["controles"].values())
def test_plantillas_tienen_encabezados_contractuales():
 assert plantilla_productos().read().startswith(b"SKU;STOCK;PRECIO_CENTAVOS;ACTIVO") and plantilla_pedidos().read().startswith(b"ID_EXTERNO")
def test_ruta_y_servicio_son_offline():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");s=Path("services/importacion_snapshot_dux.py").read_text(encoding="utf-8").lower();assert 'route("/admin/estructura/convertir-snapshot-dux"' in r
 for x in ("db.session","commit(","requests.","urlopen","http://","https://"):assert x not in s
