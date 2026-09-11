import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import pytest
from services.gestion_lotes_importacion_mp import anular_lote,construir_historial,diagnosticar_lote
def lote(estado="confirmado",tenant=2):
 vista={"filas":[{"accion":"crear","datos":{"cuenta_codigo":"MP","referencia_movimiento":"M1"}}]};return SimpleNamespace(id=1,organizacion_id=tenant,unidad_negocio_id=3,estado=estado,evidencia_json=json.dumps(vista),fecha_creacion=datetime(2026,1,1),nombre_archivo="mp.csv",cuenta_codigo="MP",movimientos_creados=1,huella_documento="a"*64)
def mov(origen="extracto_mp",estado="confirmado",tenant=2):return SimpleNamespace(organizacion_id=tenant,unidad_negocio_id=3,cuenta_codigo="MP",referencia_movimiento="M1",origen=origen,estado=estado,detalle=None)
class Sesion:
 def __init__(self):self.commits=0;self.rollbacks=0
 def commit(self):self.commits+=1
 def rollback(self):self.rollbacks+=1
def test_diagnostico_localiza_movimientos_exactos_del_tenant():
 r=diagnosticar_lote(lote(),[mov(),mov(tenant=8)],organizacion_id=2,unidad_negocio_id=3);assert r["anulable"] and r["encontrados"]==1
def test_diagnostico_bloquea_faltantes_origen_y_estado():
 assert not diagnosticar_lote(lote(),[],organizacion_id=2,unidad_negocio_id=3)["anulable"]
 assert not diagnosticar_lote(lote(),[mov("manual")],organizacion_id=2,unidad_negocio_id=3)["anulable"]
 assert not diagnosticar_lote(lote("anulado"),[mov(estado="anulado")],organizacion_id=2,unidad_negocio_id=3)["anulable"]
def test_anulacion_es_atomica_no_borra_y_no_ejecuta():
 l=lote();m=mov();s=Sesion();r=anular_lote(l,[m],"archivo incorrecto",organizacion_id=2,unidad_negocio_id=3,db_session=s)
 assert l.estado==m.estado=="anulado" and s.commits==1 and r["eliminaciones"]==r["acciones_externas"]==0
def test_motivo_es_obligatorio_y_no_hay_mutacion():
 l=lote();m=mov();s=Sesion()
 with pytest.raises(ValueError):anular_lote(l,[m],"",organizacion_id=2,unidad_negocio_id=3,db_session=s)
 assert l.estado==m.estado=="confirmado" and s.commits==0
def test_historial_filtra_y_resume():
 r=construir_historial([lote(),lote(tenant=8)],[mov()],organizacion_id=2,unidad_negocio_id=3);assert r["total"]==r["confirmados"]==1 and r["acciones_externas"]==0
def test_panel_exige_tenant_y_explica_no_devolucion():
 ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_lotes_importacion_mp.html").read_text(encoding="utf-8")
 assert "historial_lotes_mp" in ruta and "organizacion_id=organizacion.id" in ruta and "No elimina datos ni genera devoluciones externas" in html
def test_servicio_desconectado_sin_eliminaciones():
 s=Path("services/gestion_lotes_importacion_mp.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("requests","urlopen","access_token","client_secret","http://","https://","delete(","session.delete"))
