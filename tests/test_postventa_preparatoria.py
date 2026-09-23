import json
from pathlib import Path
import pytest
from services.postventa_preparatoria import crear_caso,proponer_resolucion,cambiar_estado,expediente_postventa,exportar
class O:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",O.n);O.n+=1
class S:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def pedido(**k):return O(id=1,organizacion_id=k.get("organizacion_id",7),unidad_negocio_id=9)
def caso(**k):return O(id=k.pop("id",2),organizacion_id=7,unidad_negocio_id=9,pedido_id=1,estado=k.pop("estado","abierto"),contacto_externo=False,afecta_stock=False,afecta_saldo=False,**k)
def propuesta(**k):return O(id=k.pop("id",3),organizacion_id=7,unidad_negocio_id=9,caso_id=k.pop("caso_id",2),importe_centavos=k.pop("importe_centavos",100),aprobada=False,ejecutada=False,afecta_stock=False,emite_credito=False,**k)
def test_caso_nace_abierto_y_sin_impacto():
 s=S();c=crear_caso({"tipo":"garantia","titulo":"Falla pintura","descripcion":"Se observa desprendimiento."},pedido=pedido(),organizacion_id=7,unidad_negocio_id=9,Caso=O,db_session=s);assert c.estado=="abierto" and not c.contacto_externo and not c.afecta_stock and not c.afecta_saldo and s.commits==1
def test_caso_rechaza_otro_tenant_y_datos_incompletos():
 with pytest.raises(ValueError):crear_caso({"tipo":"garantia","titulo":"Falla","descripcion":"Descripcion valida"},pedido=pedido(organizacion_id=8),organizacion_id=7,unidad_negocio_id=9,Caso=O,db_session=S())
 with pytest.raises(ValueError):crear_caso({"tipo":"otro","titulo":"x","descripcion":"corta"},pedido=pedido(),organizacion_id=7,unidad_negocio_id=9,Caso=O,db_session=S())
def test_resolucion_nace_no_aprobada_no_ejecutable():
 s=S();c=caso();p=proponer_resolucion({"tipo_resolucion":"reintegro","detalle":"Reintegro total propuesto","importe_centavos":"5000"},caso=c,pedido=pedido(),organizacion_id=7,unidad_negocio_id=9,Propuesta=O,db_session=s);assert c.estado=="propuesta" and not p.aprobada and not p.ejecutada and not p.afecta_stock and not p.emite_credito
def test_transiciones_no_permiten_ejecucion():
 c=caso();cambiar_estado(c,pedido=pedido(),organizacion_id=7,unidad_negocio_id=9,estado="diagnostico",db_session=S());assert c.estado=="diagnostico"
 with pytest.raises(ValueError):cambiar_estado(c,pedido=pedido(),organizacion_id=7,unidad_negocio_id=9,estado="ejecutado",db_session=S())
def test_resolucion_rechaza_pedido_de_otro_tenant_o_no_vinculado():
 with pytest.raises(ValueError):proponer_resolucion({"tipo_resolucion":"rechazo","detalle":"No corresponde"},caso=caso(),pedido=pedido(organizacion_id=8),organizacion_id=7,unidad_negocio_id=9,Propuesta=O,db_session=S())
 with pytest.raises(ValueError):proponer_resolucion({"tipo_resolucion":"rechazo","detalle":"No corresponde"},caso=caso(),pedido=O(id=99,organizacion_id=7,unidad_negocio_id=9),organizacion_id=7,unidad_negocio_id=9,Propuesta=O,db_session=S())
def test_expediente_detecta_huerfanos_y_efectos():
 c=caso();p=propuesta(caso_id=99);r=expediente_postventa(organizacion_id=7,unidad_negocio_id=9,casos=[c],propuestas=[p]);assert not r["aprobado"] and r["hallazgos"][0]["codigo"]=="propuesta_huerfana"
def test_expediente_firmado_reproducible():
 kw=dict(organizacion_id=7,unidad_negocio_id=9,casos=[caso()],propuestas=[propuesta()]);a=expediente_postventa(**kw);b=expediente_postventa(**kw);assert a["huella_expediente"]==b["huella_expediente"]==json.load(exportar(a))["huella_expediente"] and not any(a["controles"].values())
def test_modelo_ruta_y_servicio_mantienen_frontera():
 m=Path("models/postventa.py").read_text(encoding="utf-8");r=Path("modules/admin/postventa/routes.py").read_text(encoding="utf-8");s=Path("services/postventa_preparatoria.py").read_text(encoding="utf-8")
 assert "caso_postventa" in m and 'route("/admin/postventa")' in r
 for x in ("requests.","urlopen","aprobada=True","ejecutada=True","afecta_stock=True","emite_credito=True"):assert x not in s
