import json
from datetime import date
from pathlib import Path
import pytest
from services.preparacion_mantenimiento import agregar_tarea,proponer_repuesto,expediente_mantenimiento,exportar_expediente
class Obj:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",Obj.n);Obj.n+=1
class Session:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def test_tarea_nace_pendiente_y_tenant():
 p=Obj(id=1,organizacion_id=7,unidad_negocio_id=9);s=Session();t=agregar_tarea({"orden":1,"descripcion":"Limpiar lente"},plan=p,organizacion_id=7,unidad_negocio_id=9,Tarea=Obj,db_session=s)
 assert t.plan_id==1 and t.obligatoria and not t.completada and s.commits==1
def test_tarea_rechaza_plan_cruzado_y_orden():
 p=Obj(id=1,organizacion_id=8,unidad_negocio_id=9)
 with pytest.raises(ValueError):agregar_tarea({"orden":1,"descripcion":"X"},plan=p,organizacion_id=7,unidad_negocio_id=9,Tarea=Obj,db_session=Session())
 p.organizacion_id=7
 with pytest.raises(ValueError):agregar_tarea({"orden":0,"descripcion":"X"},plan=p,organizacion_id=7,unidad_negocio_id=9,Tarea=Obj,db_session=Session())
def test_repuesto_nace_sin_aprobacion_reserva_o_stock():
 o=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,estado="planificada");s=Session();p=proponer_repuesto({"codigo_repuesto":"F1","descripcion":"Filtro","cantidad":"2,5","costo_estimado":"1.000"},orden=o,organizacion_id=7,unidad_negocio_id=9,Propuesta=Obj,db_session=s)
 assert not p.aprobada and not p.reservado and not p.afecta_stock and p.costo_estimado_centavos==100000
def test_repuesto_rechaza_orden_cancelada_y_valores():
 o=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,estado="cancelada")
 with pytest.raises(ValueError):proponer_repuesto({"codigo_repuesto":"F","descripcion":"X","cantidad":1},orden=o,organizacion_id=7,unidad_negocio_id=9,Propuesta=Obj,db_session=Session())
def objetos():
 p=Obj(id=1,organizacion_id=7,unidad_negocio_id=9);o=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,maquina_id=4,fecha_prevista=date(2026,10,5),estado="planificada",costo_estimado_centavos=5000,ejecutada=False,afecta_stock=False)
 t=Obj(id=3,plan_id=1,completada=False);r=Obj(id=4,orden_mantenimiento_id=2,costo_estimado_centavos=2000,aprobada=False,reservado=False,afecta_stock=False);return [p],[o],[t],[r]
def test_expediente_carga_costos_y_firma():
 p,o,t,r=objetos();a=expediente_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=p,ordenes=o,tareas=t,repuestos=r);b=expediente_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=p,ordenes=o,tareas=t,repuestos=r)
 assert a["carga_semanal"][0]["ordenes"]==1 and a["costo_repuestos_centavos"]==2000 and a["aprobado"]
 assert a["huella_expediente"]==b["huella_expediente"]==json.load(exportar_expediente(a))["huella_expediente"]
def test_expediente_detecta_impactos_indebidos():
 p,o,t,r=objetos();t[0].completada=True;r[0].reservado=True
 x=expediente_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=p,ordenes=o,tareas=t,repuestos=r)
 assert not x["aprobado"] and {h["codigo"] for h in x["hallazgos"]}=={"tarea_completada_indebidamente","repuesto_con_impacto"}
def test_tablas_rutas_y_frontera_final():
 modelo=Path("models/mantenimiento.py").read_text(encoding="utf-8");rutas=Path("modules/admin/mantenimiento/routes.py").read_text(encoding="utf-8");servicio=Path("services/preparacion_mantenimiento.py").read_text(encoding="utf-8")
 assert "tarea_plan_mantenimiento" in modelo and "propuesta_repuesto_mantenimiento" in modelo and 'route("/admin/mantenimiento/expediente")' in rutas
 for x in ("requests.","urlopen","MovimientoInventario(","OrdenCompra(","aprobada=True","reservado=True","afecta_stock=True"):assert x not in servicio
