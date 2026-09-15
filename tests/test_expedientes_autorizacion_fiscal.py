from pathlib import Path
from types import SimpleNamespace
import json,pytest
from services.expedientes_autorizacion_fiscal import evaluar_borrador,certificar,exportar
def borrador(estado="listo"):
 e=SimpleNamespace(id=1,organizacion_id=7,activa=True,facturacion_habilitada=True);c=SimpleNamespace(id=2,organizacion_id=7,entidad_fiscal_id=1,estado="prueba");p=SimpleNamespace(id=3,organizacion_id=7,entidad_fiscal_id=1,estado="activo",emision_real_habilitada=False,configuracion=c);t=SimpleNamespace(id=4,punto_venta_fiscal_id=3,activo=True);i=SimpleNamespace(neto_centavos=100,iva_centavos=21,total_centavos=121)
 return SimpleNamespace(id=5,organizacion_id=7,estado=estado,cae=None,numero_autorizado=None,entidad_fiscal=e,punto_venta=p,tipo_comprobante=t,items=[i],neto_centavos=100,iva_centavos=21,total_centavos=121,referencia_externa="F-1",receptor_nombre="Ñ",receptor_documento="1",moneda="ARS")
def test_evalua_expediente_integro_y_estable():
 a=evaluar_borrador(borrador(),organizacion_id=7);b=evaluar_borrador(borrador(),organizacion_id=7);assert a["bloqueos"]==[] and a["huella"]==b["huella"] and a["puede_emitir"] is False
def test_bloquea_estado_totales_y_autorizacion():
 b=borrador("borrador");b.total_centavos=99;b.cae="x";r=evaluar_borrador(b,organizacion_id=7);assert {"estado_no_listo","totales_inconsistentes","autorizacion_preexistente"}<=set(r["bloqueos"])
def test_bloquea_cadena_tenant_y_emision_indebida():
 b=borrador();b.entidad_fiscal.organizacion_id=8;b.punto_venta.emision_real_habilitada=True;assert "entidad_no_habilitada" in evaluar_borrador(b,organizacion_id=7)["bloqueos"] and "emision_real_indebida" in evaluar_borrador(b,organizacion_id=7)["bloqueos"]
class Q:
 def filter_by(self,**k):return self
 def first(self):return None
class M:
 query=Q();n=0
 def __init__(self,**k):self.__dict__.update(k);M.n+=1;self.id=M.n
class S:
 def __init__(self):self.x=[];self.commits=0;self.rollbacks=0
 def add(self,x):self.x.append(x)
 def commit(self):self.commits+=1
 def rollback(self):self.rollbacks+=1
def test_certifica_expediente_y_evento_en_un_commit():
 s=S();e=certificar(borrador(),organizacion_id=7,usuario=SimpleNamespace(username="martín"),ExpedienteAutorizacionFiscal=M,EventoFiscal=M,db_session=s);assert e.puede_emitir is False and len(s.x)==2 and s.commits==1
def test_no_certifica_borrador_bloqueado():
 s=S()
 with pytest.raises(ValueError):certificar(borrador("borrador"),organizacion_id=7,usuario=None,ExpedienteAutorizacionFiscal=M,EventoFiscal=M,db_session=s)
 assert s.x==[]
def test_exportacion_preserva_utf8_y_bloqueo():
 e=SimpleNamespace(id=1,estado="certificado",huella="a"*64,evidencia_json=json.dumps(evaluar_borrador(borrador(),organizacion_id=7),ensure_ascii=False));assert json.loads(exportar(e).read())["puede_emitir"] is False
def test_modelo_y_panel_quedan_integrados():
 assert "puede_emitir = false" in Path("models/expediente_autorizacion_fiscal.py").read_text(encoding="utf-8")
 assert "Certificar expediente" in Path("templates/admin_expedientes_fiscales.html").read_text(encoding="utf-8") and ".query" not in Path("modules/admin/facturacion/routes.py").read_text(encoding="utf-8")
def test_servicio_sin_transporte_externo():
 s=Path("services/expedientes_autorizacion_fiscal.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("requests","urlopen","http://","https://","access_token","client_secret"))
