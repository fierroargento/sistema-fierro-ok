import json
from datetime import datetime,timedelta
from pathlib import Path
import pytest
from services.cierre_postventa import agregar_item,agregar_evidencia,control_final,exportar
class O:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",O.n);O.n+=1
class S:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def caso(**k):return O(id=k.pop("id",1),organizacion_id=7,unidad_negocio_id=9,estado=k.pop("estado","abierto"),fecha_creacion=k.pop("fecha_creacion",datetime.utcnow()),**k)
def propuesta(**k):return O(id=2,caso_id=1,importe_centavos=k.get("importe_centavos",1000))
def item(**k):return O(id=3,caso_id=1,recibido=k.get("recibido",False),afecta_stock=False)
def evidencia(**k):return O(id=4,caso_id=1,verificada=False,enviada=False)
def test_item_nace_sin_recepcion_ni_stock():
 s=S();x=agregar_item({"cantidad":"2,5","condicion":"danado","detalle_item":"Golpe"},caso=caso(),producto=O(id=8,organizacion_id=7),organizacion_id=7,unidad_negocio_id=9,Item=O,db_session=s);assert str(x.cantidad)=="2.5" and not x.recibido and not x.afecta_stock and s.commits==1
def test_item_rechaza_contexto_y_cantidad():
 with pytest.raises(ValueError):agregar_item({"cantidad":"0","condicion":"nuevo"},caso=caso(),producto=O(id=8,organizacion_id=7),organizacion_id=7,unidad_negocio_id=9,Item=O,db_session=S())
def test_evidencia_nace_interna_con_huella():
 s=S();e=agregar_evidencia({"tipo_evidencia":"foto","referencia":"foto-frente-001"},caso=caso(),organizacion_id=7,unidad_negocio_id=9,Evidencia=O,db_session=s);assert len(e.huella)==64 and not e.verificada and not e.enviada
def test_control_detecta_casos_incompletos_y_vencidos():
 c=caso(estado="diagnostico",fecha_creacion=datetime.utcnow()-timedelta(days=20));r=control_final(organizacion_id=7,unidad_negocio_id=9,casos=[c],propuestas=[],items=[],evidencias=[]);assert {x["codigo"] for x in r["hallazgos"]}=={"caso_sin_items","caso_sin_evidencia","caso_vencido"}
def test_control_completo_calcula_exposicion():
 r=control_final(organizacion_id=7,unidad_negocio_id=9,casos=[caso(estado="propuesta")],propuestas=[propuesta(importe_centavos=5000)],items=[item()],evidencias=[evidencia()]);assert r["aprobado"] and r["resumen"]["exposicion_centavos"]==5000 and not any(r["controles"].values())
def test_control_firmado_reproducible():
 kw=dict(organizacion_id=7,unidad_negocio_id=9,casos=[],propuestas=[],items=[],evidencias=[],ahora=datetime(2026,1,1));a=control_final(**kw);b=control_final(**kw);assert a["huella_control"]==b["huella_control"]==json.load(exportar(a))["huella_control"]
def test_modelo_ruta_y_servicio_sin_efectos():
 m=Path("models/postventa.py").read_text(encoding="utf-8");r=Path("modules/admin/postventa/routes.py").read_text(encoding="utf-8");s=Path("services/cierre_postventa.py").read_text(encoding="utf-8")
 assert "item_caso_postventa" in m and "evidencia_caso_postventa" in m and 'accion=="agregar_item"' in r
 for x in ("requests.","urlopen","recibido=True","afecta_stock=True","verificada=True","enviada=True"):assert x not in s
