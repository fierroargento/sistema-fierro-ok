import json
from datetime import date,datetime
from pathlib import Path
import pytest
from services.cierre_personas_preparatorio import registrar_competencia,expediente_personas,exportar_expediente

class Obj:
 n=1
 def __init__(s,**k):s.__dict__.update(k);s.id=getattr(s,"id",Obj.n);Obj.n+=1
class Session:
 def __init__(s):s.o=[];s.commits=0
 def add(s,x):s.o.append(x)
 def commit(s):s.commits+=1
def empleado(**k):return Obj(id=k.pop("id",1),organizacion_id=k.pop("organizacion_id",7),unidad_negocio_id=k.pop("unidad_negocio_id",9),tipo_registro="empleado",**k)
def turno(**k):return Obj(id=k.pop("id",1),empleado_id=k.pop("empleado_id",1),organizacion_id=7,unidad_negocio_id=9,inicio=k.pop("inicio",datetime(2026,10,1,8)),fin=k.pop("fin",datetime(2026,10,1,16)),sector=k.pop("sector","Taller"),estado="planificado",confirmado=False,afecta_nomina=False,**k)
def novedad(**k):return Obj(id=k.pop("id",2),empleado_id=k.pop("empleado_id",1),organizacion_id=7,unidad_negocio_id=9,tipo=k.pop("tipo","ausencia"),fecha_desde=k.pop("fecha_desde",date(2026,10,1)),fecha_hasta=k.pop("fecha_hasta",date(2026,10,1)),minutos_propuestos=k.pop("minutos_propuestos",0),estado="propuesta",aprobada=False,afecta_nomina=False,**k)
def competencia(**k):return Obj(id=k.pop("id",3),empleado_id=k.pop("empleado_id",1),organizacion_id=7,unidad_negocio_id=9,vence_el=k.pop("vence_el",date(2026,10,20)),verificada=False,habilita_asignacion=False,**k)

def test_competencia_nace_no_verificada_y_no_habilitante():
 s=Session();c=registrar_competencia({"codigo":"SOLD","nombre":"Soldadura","nivel":"3","vence_el":"2026-10-20"},empleado=empleado(),organizacion_id=7,unidad_negocio_id=9,Competencia=Obj,db_session=s)
 assert c.codigo=="SOLD" and c.nivel==3 and not c.verificada and not c.habilita_asignacion and s.commits==1

def test_competencia_rechaza_contexto_y_nivel():
 with pytest.raises(ValueError):registrar_competencia({"codigo":"X","nombre":"X","nivel":"6"},empleado=empleado(),organizacion_id=7,unidad_negocio_id=9,Competencia=Obj,db_session=Session())
 with pytest.raises(ValueError):registrar_competencia({"codigo":"X","nombre":"X","nivel":"1"},empleado=empleado(organizacion_id=8),organizacion_id=7,unidad_negocio_id=9,Competencia=Obj,db_session=Session())

def test_expediente_calcula_cobertura_y_horas_extra_propuestas():
 r=expediente_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[empleado()],turnos=[turno()],novedades=[novedad(tipo="horas_extra",minutos_propuestos=90)],competencias=[],hoy=date(2026,10,1))
 assert r["cobertura_diaria"]==[{"fecha":"2026-10-01","sector":"Taller","empleados":1,"minutos_planificados":480}]
 assert r["minutos_extra_propuestos"]==90 and r["aprobado"]

def test_expediente_detecta_turno_con_ausencia():
 r=expediente_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[empleado()],turnos=[turno()],novedades=[novedad()],competencias=[],hoy=date(2026,10,1))
 assert not r["aprobado"] and r["hallazgos"][0]["codigo"]=="turno_con_ausencia"

def test_expediente_clasifica_vencimientos():
 cs=[competencia(id=1,vence_el=date(2026,9,30)),competencia(id=2,vence_el=date(2026,10,20)),competencia(id=3,vence_el=date(2027,1,1))]
 r=expediente_personas(organizacion_id=7,unidad_negocio_id=9,empleados=[empleado()],turnos=[],novedades=[],competencias=cs,hoy=date(2026,10,1))
 assert [x["estado"] for x in r["vencimientos_competencias"]]==["vencida","proxima","vigente_no_verificada"]

def test_expediente_es_reproducible_y_sin_efectos():
 kw=dict(organizacion_id=7,unidad_negocio_id=9,empleados=[empleado()],turnos=[],novedades=[],competencias=[],hoy=date(2026,10,1));a=expediente_personas(**kw);b=expediente_personas(**kw)
 assert a["huella_expediente"]==b["huella_expediente"]==json.load(exportar_expediente(a))["huella_expediente"]
 assert not any(a["controles"].values())

def test_modelo_rutas_y_servicio_mantienen_frontera():
 modelo=Path("models/personas.py").read_text(encoding="utf-8");rutas=Path("modules/admin/personas/routes.py").read_text(encoding="utf-8");servicio=Path("services/cierre_personas_preparatorio.py").read_text(encoding="utf-8")
 assert "competencia_empleado_preparatoria" in modelo and 'route("/admin/personas/expediente")' in rutas and "CompetenciaEmpleadoPreparatoria" in Path("app.py").read_text(encoding="utf-8")
 for x in ("requests.","urlopen","ReciboSueldo(","verificada=True","habilita_asignacion=True","aprobada=True","afecta_nomina=True"):assert x not in servicio
