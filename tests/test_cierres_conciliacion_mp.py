import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from services.cierres_conciliacion_mp import decidir_cierre,huella_snapshot,snapshot_conciliacion

def venta():return SimpleNamespace(id=1,organizacion_id=2,unidad_negocio_id=3,cuenta_codigo="MP",referencia_venta="V",referencia_pago="P",estado="confirmada",liquidacion_esperada_centavos=100,piso_unitario_snapshot_centavos=90,cantidad=1,importe_bruto_centavos=120)
def mov():return SimpleNamespace(id=2,organizacion_id=2,unidad_negocio_id=3,cuenta_codigo="MP",referencia_venta="V",referencia_pago="P",referencia_movimiento="M",impacta_saldo=True,estado="confirmado",importe_centavos=100,direccion="credito")
class Evento:
 def __init__(self,**k):self.__dict__.update(k)
class Sesion:
 def __init__(self):self.items=[];self.commits=0
 def add(self,x):self.items.append(x)
 def commit(self):self.commits+=1

def cierre(estado="revision"):
 snap=snapshot_conciliacion([venta()],[mov()],[])
 return SimpleNamespace(id=4,organizacion_id=2,unidad_negocio_id=3,estado=estado,puede_ejecutar=False,huella_origen=huella_snapshot(snap),certificacion_json=json.dumps({"aprobada":True}),motivo=None,decidido_por_username=None,fecha_decision=None,snapshot_json=json.dumps(snap),eventos=[]),snap

def test_snapshot_es_estable_y_economico():
 a=snapshot_conciliacion([venta()],[mov()],[]);b=snapshot_conciliacion([venta()],[mov()],[])
 assert huella_snapshot(a)==huella_snapshot(b) and a["filas"][0]["diferencia"]==0
def test_aprueba_y_cierra_sin_habilitar_ejecucion():
 c,snap=cierre();ses=Sesion();decidir_cierre(c,"aprobar","",usuario=SimpleNamespace(username="admin"),snapshot_actual=snap,EventoCierreConciliacionMP=Evento,db_session=ses);decidir_cierre(c,"cerrar","ticket",usuario=SimpleNamespace(username="admin"),snapshot_actual=snap,EventoCierreConciliacionMP=Evento,db_session=ses)
 assert c.estado=="cerrado" and c.puede_ejecutar is False and len(ses.items)==2
def test_cambio_de_datos_vuelve_obsoleto():
 c,snap=cierre();snap["movimientos_ids"].append(99);r=decidir_cierre(c,"aprobar","",usuario=None,snapshot_actual=snap,EventoCierreConciliacionMP=Evento,db_session=Sesion());assert r["estado"]=="obsoleto"
def test_certificacion_bloqueada_no_aprueba():
 c,snap=cierre();c.certificacion_json=json.dumps({"aprobada":False})
 with pytest.raises(ValueError):decidir_cierre(c,"aprobar","",usuario=None,snapshot_actual=snap,EventoCierreConciliacionMP=Evento,db_session=Sesion())
def test_panel_tenant_y_flujo_completo():
 ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
 assert ruta.count("CierreMP.query.filter_by")>=2 and "organizacion_id=organizacion.id" in ruta
 for accion in ("guardar_cierre_mp","enviar_revision_cierre_mp","aprobar_cierre_mp","cerrar_cierre_mp","exportar_cierre_mp"):assert f'value="{accion}"' in html
def test_contrato_desconectado():
 fuente=Path("services/cierres_conciliacion_mp.py").read_text(encoding="utf-8").lower();modelo=Path("models/cierre_conciliacion_mp.py").read_text(encoding="utf-8").lower()
 assert not any(x in fuente for x in ("requests","urlopen","access_token","client_secret","http://","https://"));assert "puede_ejecutar = false" in modelo
