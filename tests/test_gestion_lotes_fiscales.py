import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from services.gestion_lotes_fiscales import obtener_lote, referencias_lote, exportar_lote, anular_lote

def evidencia():return json.dumps({"comprobantes":[{"referencia":"F-1"},{"referencia":"F-2"}]})
def lote(estado="confirmado",tenant=7):return SimpleNamespace(id=8,organizacion_id=tenant,nombre_archivo="ñ.csv",huella_documento="a"*64,huella_plan="b"*64,estado=estado,comprobantes_creados=2,items_creados=3,rechazados=0,evidencia_json=evidencia(),emision_real=False,creado_por_username="martín",fecha_creacion="2026-09-15")
def borrador(ref="F-1",estado="borrador"):return SimpleNamespace(id=1,organizacion_id=7,referencia_externa=ref,estado=estado,cae=None,numero_autorizado=None)
class Consulta:
 def __init__(self,resultado):self.resultado=resultado
 def filter_by(self,**kw):self.kw=kw;return self
 def filter(self,*args):return self
 def first(self):return self.resultado[0] if self.resultado else None
 def all(self):return self.resultado
class Campo:
 def in_(self,x):return x
class ModeloB:referencia_externa=Campo()
class Evento:
 def __init__(self,**kw):self.__dict__.update(kw)
class Sesion:
 def __init__(self,fallar=False):self.items=[];self.commits=0;self.rollbacks=0;self.fallar=fallar
 def add(self,x):self.items.append(x)
 def commit(self):
  if self.fallar:raise RuntimeError("fallo")
  self.commits+=1
 def rollback(self):self.rollbacks+=1
def preparar_modelo(items):
 class M(ModeloB):pass
 M.query=Consulta(items);return M
def test_referencias_y_exportacion_preservan_evidencia_utf8():
 l=lote();assert referencias_lote(l)==["F-1","F-2"]
 doc=json.loads(exportar_lote(l).read());assert doc["emision_real"] is False and doc["nombre_archivo"]=="ñ.csv"
def test_obtencion_exige_lote_del_tenant():
 class L:query=Consulta([])
 with pytest.raises(ValueError):obtener_lote(L,organizacion_id=7,lote_id=9)
def test_anulacion_cancela_borradores_y_audita_en_un_commit():
 bs=[borrador("F-1"),borrador("F-2","listo")];s=Sesion();r=anular_lote(lote(),motivo="duplicado",usuario=SimpleNamespace(username="martín"),BorradorComprobanteFiscal=preparar_modelo(bs),EventoFiscal=Evento,db_session=s)
 assert r=={"lote_id":8,"borradores_cancelados":2,"estado":"anulado"} and all(b.estado=="cancelado" for b in bs)
 assert len(s.items)==2 and s.commits==1 and "duplicado" in s.items[0].detalle
def test_anulacion_rechaza_autorizado_sin_escribir():
 b=borrador();b.cae="123";s=Sesion()
 with pytest.raises(ValueError):anular_lote(lote(),motivo="x",usuario=None,BorradorComprobanteFiscal=preparar_modelo([b,borrador("F-2")]),EventoFiscal=Evento,db_session=s)
 assert s.items==[] and s.commits==0
def test_anulacion_exige_integridad_y_motivo():
 with pytest.raises(ValueError):anular_lote(lote(),motivo="",usuario=None,BorradorComprobanteFiscal=preparar_modelo([]),EventoFiscal=Evento,db_session=Sesion())
 with pytest.raises(ValueError):anular_lote(lote(),motivo="x",usuario=None,BorradorComprobanteFiscal=preparar_modelo([borrador()]),EventoFiscal=Evento,db_session=Sesion())
def test_error_de_commit_hace_rollback():
 s=Sesion(True)
 with pytest.raises(RuntimeError):anular_lote(lote(),motivo="x",usuario=None,BorradorComprobanteFiscal=preparar_modelo([borrador(),borrador("F-2")]),EventoFiscal=Evento,db_session=s)
 assert s.rollbacks==1
def test_panel_no_consulta_modelos_directamente():
 ruta=Path("modules/admin/facturacion/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_lotes_fiscales.html").read_text(encoding="utf-8")
 assert ".query" not in ruta and "Anular internamente" in html and "Descargar JSON" in html
def test_servicio_no_tiene_transporte_ni_borrado():
 fuente=Path("services/gestion_lotes_fiscales.py").read_text(encoding="utf-8").lower()
 assert not any(x in fuente for x in ("requests","urlopen","http://","https://","delete(","access_token","client_secret"))
