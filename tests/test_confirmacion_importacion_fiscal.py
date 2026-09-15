from types import SimpleNamespace
from pathlib import Path
import copy
import pytest
from services.importacion_borradores_fiscales import previsualizar_borradores, validar_confirmacion, confirmar_importacion, deserializar_previsualizacion, exportar_previsualizacion

def base():
 e=SimpleNamespace(id=1,organizacion_id=7,cuit="30712345678");p=SimpleNamespace(id=2,organizacion_id=7,entidad_fiscal_id=1,numero=4);t=SimpleNamespace(id=3,punto_venta_fiscal_id=2,codigo_arca=6,punto_venta=p);return e,p,t
def vista():
 e,p,t=base();csv=b"referencia;entidad_fiscal;punto_venta;codigo_arca;receptor;descripcion;cantidad;precio_unitario;alicuota_iva\nF-1;30712345678;4;6;Cliente;Producto;2;121;21\n";return previsualizar_borradores(csv,organizacion_id=7,entidades=[e],puntos=[p],tipos=[t])
def validar(v,**kw):
 e,p,t=base();return validar_confirmacion(v,organizacion_id=7,entidades=[e],puntos=[p],tipos=[t],referencias_existentes=kw.get("referencias",()),huellas_existentes=kw.get("huellas",()))
def test_revalidacion_acepta_plan_integro(): assert validar(vista())["resumen"]["preparados"]==1
def test_revalidacion_bloquea_tenant_y_repeticion():
 v=vista();v["organizacion_id"]=8
 with pytest.raises(ValueError):validar(v)
 v=vista()
 with pytest.raises(ValueError):validar(v,referencias=["F-1"])
 with pytest.raises(ValueError):validar(v,huellas=[v["huella_documento"]])
def test_revalidacion_detecta_manipulacion_de_importes():
 v=vista();v["comprobantes"][0]["total_centavos"]+=1
 with pytest.raises(ValueError):validar(v)
def test_deserializacion_acotada():
 assert deserializar_previsualizacion(exportar_previsualizacion(vista()).read())["organizacion_id"]==7
 with pytest.raises(ValueError):deserializar_previsualizacion("{}")
class Modelo:
 secuencia=0
 def __init__(self,**kw):self.__dict__.update(kw);Modelo.secuencia+=1;self.id=Modelo.secuencia
class Sesion:
 def __init__(self,fallar=False):self.items=[];self.commits=0;self.rollbacks=0;self.fallar=fallar
 def add(self,x):self.items.append(x)
 def flush(self):
  if self.fallar:raise RuntimeError("fallo")
 def commit(self):self.commits+=1
 def rollback(self):self.rollbacks+=1
def test_confirmacion_crea_lote_borrador_item_evento_en_un_commit():
 s=Sesion();l=confirmar_importacion(vista(),organizacion_id=7,usuario=SimpleNamespace(id=9,username="martín"),nombre_archivo="fiscal.csv",BorradorComprobanteFiscal=Modelo,BorradorItemFiscal=Modelo,EventoFiscal=Modelo,LoteImportacionFiscal=Modelo,db_session=s)
 assert l.emision_real is False and l.comprobantes_creados==1 and l.items_creados==1 and len(s.items)==4 and s.commits==1
 assert s.items[1].estado=="borrador" and s.items[1].cae is None and s.items[1].numero_autorizado is None
def test_error_revierte_toda_la_transaccion():
 s=Sesion(True)
 with pytest.raises(RuntimeError):confirmar_importacion(vista(),organizacion_id=7,usuario=None,nombre_archivo="x.csv",BorradorComprobanteFiscal=Modelo,BorradorItemFiscal=Modelo,EventoFiscal=Modelo,LoteImportacionFiscal=Modelo,db_session=s)
 assert s.commits==0 and s.rollbacks==1
def test_modelo_impone_unicidad_y_emision_bloqueada():
 fuente=Path("models/lote_importacion_fiscal.py").read_text(encoding="utf-8")
 assert "UniqueConstraint" in fuente and "emision_real = false" in fuente
def test_panel_confirma_solo_lotes_aprobados():
 ruta=Path("modules/admin/facturacion/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_importacion_borradores_fiscales.html").read_text(encoding="utf-8")
 assert "validar_confirmacion(" in ruta and "confirmar_importacion(" in ruta and "vista.resumen.rechazados == 0" in html and ".query" not in ruta
def test_servicio_no_contiene_transporte_externo():
 fuente=Path("services/importacion_borradores_fiscales.py").read_text(encoding="utf-8").lower()
 assert not any(x in fuente for x in ("requests","urlopen","access_token","client_secret","http://","https://"))
