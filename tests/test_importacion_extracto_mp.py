from pathlib import Path
from types import SimpleNamespace
import pytest
from services.importacion_extracto_mp import previsualizar_extracto_mp,serializar_vista,deserializar_vista,aplicar_extracto_mp,validar_confirmacion

def venta(tenant=2):return SimpleNamespace(organizacion_id=tenant,unidad_negocio_id=3,cuenta_codigo="MP-1",referencia_venta="V-1")
def mov(id="M-0",tenant=2):return SimpleNamespace(organizacion_id=tenant,unidad_negocio_id=3,cuenta_codigo="MP-1",referencia_movimiento=id)
def csv_mp(neto="900,50",estado="approved"):
 return ("MOVEMENT_ID;SOURCE_ID;PAYMENT_ID;DATE_CREATED;NET_AMOUNT;STATUS;DESCRIPTION\nM-1;V-1;P-1;2026-09-10 10:30:00;"+neto+";"+estado+";Liquidación\n").encode("utf-8")
def test_normaliza_csv_mp_y_preserva_centavos():
 r=previsualizar_extracto_mp(csv_mp(),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3)
 assert r["resumen"]=={"total":1,"validos":1,"rechazados":0,"acciones_externas":0};assert r["filas"][0]["datos"]["importe_centavos"]==90050
def test_importe_negativo_se_convierte_en_debito():
 r=previsualizar_extracto_mp(csv_mp("-12,34"),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3)
 assert r["filas"][0]["datos"]["direccion"]=="debito" and r["filas"][0]["datos"]["importe_centavos"]==1234
def test_rechaza_duplicado_venta_ajena_y_cancelado():
 r=previsualizar_extracto_mp(csv_mp(estado="cancelled"),cuenta_codigo="MP-1",ventas=[venta(8)],movimientos_existentes=[mov("M-1")],organizacion_id=2,unidad_negocio_id=3)
 assert r["resumen"]["rechazados"]==1 and len(r["filas"][0]["errores"])==3
def test_serializacion_acotada_y_reversible():
 r=previsualizar_extracto_mp(csv_mp(),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3)
 assert deserializar_vista(serializar_vista(r))["filas"][0]["datos"]["referencia_movimiento"]=="M-1"
class Sesion:
 def __init__(self):self.commits=0;self.rollbacks=0;self.items=[]
 def add(self,x):self.items.append(x)
 def commit(self):self.commits+=1
 def rollback(self):self.rollbacks+=1
class Modelo:
 def __init__(self,**k):self.__dict__.update(k)
class ConsultaLote:
 def filter_by(self,**k):return self
 def first(self):return None
class Lote:
 query=ConsultaLote()
 def __init__(self,**k):self.__dict__.update(k);self.id=7
def test_aplicacion_es_transaccional_y_offline():
 vista=previsualizar_extracto_mp(csv_mp(),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3);ses=Sesion()
 lote=aplicar_extracto_mp(vista,organizacion_id=2,unidad_negocio_id=3,usuario=None,nombre_archivo="mp.csv",MovimientoLiquidacionCanal=Modelo,LoteImportacionMP=Lote,db_session=ses)
 assert lote.movimientos_creados==1 and ses.commits==1 and ses.items[1].origen=="extracto_mp"
def test_lote_con_rechazos_no_escribe():
 vista=previsualizar_extracto_mp(csv_mp(estado="cancelled"),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3);ses=Sesion()
 with pytest.raises(ValueError):aplicar_extracto_mp(vista,organizacion_id=2,unidad_negocio_id=3,usuario=None,nombre_archivo="mp.csv",MovimientoLiquidacionCanal=Modelo,LoteImportacionMP=Lote,db_session=ses)
 assert ses.items==[] and ses.commits==0
def test_confirmacion_revalida_tenant_duplicados_y_contrato():
 vista=previsualizar_extracto_mp(csv_mp(),cuenta_codigo="MP-1",ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3)
 assert validar_confirmacion(vista,ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3) is vista
 vista["filas"][0]["datos"]["direccion"]="credito_alterado"
 with pytest.raises(ValueError):validar_confirmacion(vista,ventas=[venta()],movimientos_existentes=[],organizacion_id=2,unidad_negocio_id=3)
def test_panel_y_contrato_desconectado():
 ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_importacion_extracto_mp.html").read_text(encoding="utf-8");fuente=Path("services/importacion_extracto_mp.py").read_text(encoding="utf-8").lower()
 assert "importacion_extracto_mp" in ruta and 'value="previsualizar"' in html and 'value="confirmar"' in html
 assert not any(x in fuente for x in ("requests","urlopen","access_token","client_secret","http://","https://"))
