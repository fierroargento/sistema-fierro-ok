import json
from datetime import date
from pathlib import Path
import pytest
from services.mantenimiento_nucleo import crear_plan,crear_orden,cancelar_orden,controlar_mantenimiento,exportar_control
class Obj:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",Obj.n);Obj.n+=1
class Session:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def maquina():return Obj(id=1,organizacion_id=7,unidad_negocio_id=9,codigo="laser",nombre="Laser")
def test_plan_nace_inactivo_y_sin_ejecucion():
 s=Session();p=crear_plan({"codigo":"P1","nombre":"Limpieza","frecuencia_dias":"30","proxima_fecha":"2026-10-01"},maquina=maquina(),organizacion_id=7,unidad_negocio_id=9,Plan=Obj,db_session=s)
 assert not p.activo and not p.ejecucion_habilitada and p.frecuencia_dias==30 and s.commits==1
def test_plan_rechaza_maquina_cruzada_y_frecuencia():
 m=maquina();m.organizacion_id=8
 with pytest.raises(ValueError):crear_plan({"codigo":"P","nombre":"X","frecuencia_dias":1,"proxima_fecha":"2026-10-01"},maquina=m,organizacion_id=7,unidad_negocio_id=9,Plan=Obj,db_session=Session())
 with pytest.raises(ValueError):crear_plan({"codigo":"P","nombre":"X","frecuencia_dias":0,"proxima_fecha":"2026-10-01"},maquina=maquina(),organizacion_id=7,unidad_negocio_id=9,Plan=Obj,db_session=Session())
def test_orden_nace_planificada_sin_stock():
 m=maquina();p=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,maquina_id=1);s=Session();o=crear_orden({"tipo":"preventivo","fecha_prevista":"2026-10-02","descripcion":"Revision","costo_estimado":"1.000,50"},maquina=m,plan=p,organizacion_id=7,unidad_negocio_id=9,Orden=Obj,db_session=s)
 assert o.estado=="planificada" and not o.ejecutada and not o.afecta_stock and o.costo_estimado_centavos==100050
def test_cancelacion_conserva_historial():
 o=Obj(id=4,organizacion_id=7,unidad_negocio_id=9,estado="planificada",ejecutada=False,afecta_stock=False);s=Session();cancelar_orden(o,organizacion_id=7,unidad_negocio_id=9,motivo="Cambio de fecha",db_session=s)
 assert o.estado=="cancelada" and "Cambio de fecha" in o.observacion and s.commits==1
def test_control_agenda_costos_y_hallazgos():
 p=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,maquina_id=1,proxima_fecha=date(2026,10,5),activo=False,ejecucion_habilitada=False)
 o=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,estado="planificada",costo_estimado_centavos=5000,ejecutada=False,afecta_stock=False)
 r=controlar_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=[p],ordenes=[o],hoy=date(2026,10,1))
 assert r["agenda"][0]["estado"]=="proximo" and r["costo_estimado_centavos"]==5000 and r["aprobado"]
 p.activo=True;assert not controlar_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=[p],ordenes=[],hoy=date(2026,10,1))["aprobado"]
def test_control_firmado_y_reproducible():
 a=controlar_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=[],ordenes=[],hoy=date(2026,10,1));b=controlar_mantenimiento(organizacion_id=7,unidad_negocio_id=9,planes=[],ordenes=[],hoy=date(2026,10,1))
 assert a["huella_mantenimiento"]==b["huella_mantenimiento"]==json.load(exportar_control(a))["huella_mantenimiento"]
def test_modulo_visible_y_frontera_bloqueada():
 rutas=Path("modules/admin/mantenimiento/routes.py").read_text(encoding="utf-8");base=Path("templates/base.html").read_text(encoding="utf-8");servicio=Path("services/mantenimiento_nucleo.py").read_text(encoding="utf-8")
 assert 'route("/admin/mantenimiento")' in rutas and "admin_mantenimiento.panel" in base
 for x in ("requests.","urlopen","MovimientoInventario(","OrdenCompra(","ejecutada=True","afecta_stock=True"):assert x not in servicio
