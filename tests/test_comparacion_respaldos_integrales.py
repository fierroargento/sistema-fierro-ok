import hashlib,io,json
from pathlib import Path
import pytest
from services.comparacion_respaldos_integrales import comparar,exportar

def respaldo(registros,org=7,unidad=3):
 d={"version":1,"organizacion_id":org,"unidad_negocio_id":unidad,"generado_en":"2026-09-22T10:00:00+00:00","conjuntos":{"pedidos":registros}}
 d["huella_respaldo"]=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest();return io.BytesIO(json.dumps(d).encode())
def test_detecta_altas_bajas_y_cambios_sin_restaurar():
 a=respaldo([{"_modelo":"Pedido","id":1,"estado":"A"},{"_modelo":"Pedido","id":2,"estado":"A"}]);p=respaldo([{"_modelo":"Pedido","id":1,"estado":"B"},{"_modelo":"Pedido","id":3,"estado":"A"}]);r=comparar(a,p,organizacion_id=7,unidad_negocio_id=3);assert r["resumen"]=={"conjuntos":1,"altas":1,"bajas":1,"cambios":1,"hallazgos":1};assert r["restauracion_autorizada"] is False
def test_sin_perdidas_admite_altas_y_firma():
 a=respaldo([{"_modelo":"Pedido","id":1}]);p=respaldo([{"_modelo":"Pedido","id":1},{"_modelo":"Pedido","id":2}]);r=comparar(a,p,organizacion_id=7,unidad_negocio_id=3);assert r["estado"]=="sin_perdidas_detectadas" and len(r["huella_comparacion"])==64;assert json.loads(exportar(r).read())["resumen"]["altas"]==1
def test_rechaza_firma_tenant_y_unidad():
 malo=json.loads(respaldo([]).read());malo["conjuntos"]["pedidos"].append({"id":1})
 with pytest.raises(ValueError,match="huella"):comparar(io.BytesIO(json.dumps(malo).encode()),respaldo([]),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otro tenant"):comparar(respaldo([],org=8),respaldo([],org=8),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otra unidad"):comparar(respaldo([],unidad=4),respaldo([],unidad=4),organizacion_id=7,unidad_negocio_id=3)
def test_detecta_registros_sin_identidad():
 r=comparar(respaldo([{"nombre":"x"}]),respaldo([{"nombre":"x"}]),organizacion_id=7,unidad_negocio_id=3);assert "registros_sin_identidad" in {x["codigo"] for x in r["hallazgos"]}
def test_frontera_offline_y_sin_persistencia():
 s=Path("services/comparacion_respaldos_integrales.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","rollback(","requests.","urlopen","http://","https://"));assert '"restauraciones": 0' in s
def test_ruta_y_panel():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_comparacion_respaldos_integrales.html").read_text(encoding="utf-8");assert "comparar_respaldos(" in r and "resolver_acceso()" in r;assert "No restaura bases" in h

