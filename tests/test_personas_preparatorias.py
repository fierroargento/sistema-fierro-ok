import json
from datetime import datetime,date
from pathlib import Path
import pytest
from services.personas_preparatorias import crear_turno,crear_novedad,cancelar,controlar_personas,exportar_control
class Obj:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",Obj.n);Obj.n+=1
class Session:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def empleado():return Obj(id=1,organizacion_id=7,unidad_negocio_id=9,tipo_registro="empleado",sector="Taller")
def test_turno_nace_planificado_sin_fichaje_nomina():
 s=Session();t=crear_turno({"inicio":"2026-10-01T08:00","fin":"2026-10-01T16:00","sector":"Taller","tarea":"Corte"},empleado=empleado(),organizacion_id=7,unidad_negocio_id=9,Turno=Obj,db_session=s)
 assert t.estado=="planificado" and not t.confirmado and not t.afecta_nomina and s.commits==1
def test_turno_rechaza_cruces_duracion_y_recurso():
 e=empleado();e.organizacion_id=8
 with pytest.raises(ValueError):crear_turno({"inicio":"2026-10-01T08:00","fin":"2026-10-01T16:00"},empleado=e,organizacion_id=7,unidad_negocio_id=9,Turno=Obj,db_session=Session())
 e.organizacion_id=7
 with pytest.raises(ValueError):crear_turno({"inicio":"2026-10-01T08:00","fin":"2026-10-02T08:00"},empleado=e,organizacion_id=7,unidad_negocio_id=9,Turno=Obj,db_session=Session())
def test_novedades_nacen_propuestas_y_no_liquidables():
 s=Session();n=crear_novedad({"tipo":"horas_extra","fecha_desde":"2026-10-01","fecha_hasta":"2026-10-01","minutos_propuestos":"60","detalle":"Pedido urgente"},empleado=empleado(),organizacion_id=7,unidad_negocio_id=9,Novedad=Obj,db_session=s)
 assert n.estado=="propuesta" and not n.aprobada and not n.afecta_nomina and n.minutos_propuestos==60
def test_novedad_valida_tipo_rango_y_minutos():
 for d in ({"tipo":"otro","fecha_desde":"2026-10-01","fecha_hasta":"2026-10-01","detalle":"x"},{"tipo":"ausencia","fecha_desde":"2026-10-02","fecha_hasta":"2026-10-01","detalle":"x"},{"tipo":"licencia","fecha_desde":"2026-10-01","fecha_hasta":"2026-10-01","minutos_propuestos":10,"detalle":"x"}):
  with pytest.raises(ValueError):crear_novedad(d,empleado=empleado(),organizacion_id=7,unidad_negocio_id=9,Novedad=Obj,db_session=Session())
def test_cancelacion_conserva_historial():
 x=Obj(id=3,organizacion_id=7,unidad_negocio_id=9,estado="planificado",confirmado=False,afecta_nomina=False);s=Session();cancelar(x,organizacion_id=7,unidad_negocio_id=9,motivo="Cambio operativo",db_session=s)
 assert x.estado=="cancelado" and "Cambio operativo" in x.observacion and s.commits==1
def test_control_detecta_superposiciones_y_firma():
 e=empleado();a=Obj(id=1,empleado_id=1,organizacion_id=7,unidad_negocio_id=9,inicio=datetime(2026,10,1,8),fin=datetime(2026,10,1,14),estado="planificado",confirmado=False,afecta_nomina=False);b=Obj(id=2,empleado_id=1,organizacion_id=7,unidad_negocio_id=9,inicio=datetime(2026,10,1,13),fin=datetime(2026,10,1,18),estado="planificado",confirmado=False,afecta_nomina=False)
 r=controlar_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[e],turnos=[a,b],novedades=[]);assert not r["aprobado"] and r["hallazgos"][0]["codigo"]=="turnos_superpuestos"
 x=controlar_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[e],turnos=[a],novedades=[]);y=controlar_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[e],turnos=[a],novedades=[]);assert x["huella_personas"]==y["huella_personas"]==json.load(exportar_control(x))["huella_personas"]
def test_modulo_tablas_y_frontera_sin_nomina():
 modelo=Path("models/personas.py").read_text(encoding="utf-8");rutas=Path("modules/admin/personas/routes.py").read_text(encoding="utf-8");servicio=Path("services/personas_preparatorias.py").read_text(encoding="utf-8")
 assert "turno_laboral_planificado" in modelo and "novedad_laboral_preparatoria" in modelo and 'route("/admin/personas")' in rutas
 for x in ("requests.","urlopen","ReciboSueldo(","confirmado=True","aprobada=True","afecta_nomina=True"):assert x not in servicio
