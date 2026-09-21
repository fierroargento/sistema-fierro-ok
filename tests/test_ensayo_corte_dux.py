import io,json
from pathlib import Path
import pytest
from services.ensayo_corte_dux import ensayar_corte,exportar_ensayo
def archivo(productos,pedidos=(),org=None):
 d={"productos":productos,"pedidos_abiertos":[{"id_externo":x} for x in pedidos]}
 if org is not None:d["organizacion_id"]=org
 return io.BytesIO(json.dumps(d).encode())
def producto(sku="A",stock=2,precio=100,activo=True):return {"sku":sku,"stock":stock,"precio_centavos":precio,"activo":activo}
def test_snapshots_iguales_aprueban_ensayo_sin_autorizar_corte():
 r=ensayar_corte(archivo([producto()],['P1']),archivo([producto()],['P1'],7),organizacion_id=7);assert r["aprobado"] and not r["autorizacion_corte"] and not any(r["controles"].values())
def test_detecta_stock_precio_estado_y_skus():
 a=[producto("A",2,100,True),producto("B")];b=[producto("A",3,120,False),producto("C")];r=ensayar_corte(archivo(a),archivo(b,org=7),organizacion_id=7);assert {x["tipo"] for x in r["diferencias_productos"]}=={"stock","precio_centavos","activo","faltante_fierro","solo_fierro"}
def test_detecta_diferencias_de_pedidos():
 r=ensayar_corte(archivo([producto()],['P1','P2']),archivo([producto()],['P2','P3'],7),organizacion_id=7);assert r["pedidos_abiertos"]=={"faltantes_fierro":["P1"],"solo_fierro":["P3"],"coincidentes":1}
def test_detecta_duplicados():
 r=ensayar_corte(archivo([producto(),producto()],['P1','P1']),archivo([producto()],['P1'],7),organizacion_id=7);assert {x["codigo"] for x in r["hallazgos"]}>={"sku_duplicado","pedido_duplicado"}
def test_rechaza_otro_tenant_y_archivos_invalidos():
 with pytest.raises(ValueError,match="otro tenant"):ensayar_corte(archivo([]),archivo([],org=9),organizacion_id=7)
 with pytest.raises(ValueError):ensayar_corte(io.BytesIO(b"{}"),archivo([],org=7),organizacion_id=7)
def test_firma_reproducible_y_exportable():
 a=ensayar_corte(archivo([producto()]),archivo([producto()],org=7),organizacion_id=7);b=ensayar_corte(archivo([producto()]),archivo([producto()],org=7),organizacion_id=7);assert a["huella_ensayo"]==b["huella_ensayo"]==json.load(exportar_ensayo(a))["huella_ensayo"]
def test_ruta_y_servicio_sin_conexiones_o_persistencia():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");s=Path("services/ensayo_corte_dux.py").read_text(encoding="utf-8").lower();assert 'route("/admin/estructura/ensayo-corte-dux"' in r
 for x in ("db.session","commit(","requests.","urlopen","http://","https://"):assert x not in s
