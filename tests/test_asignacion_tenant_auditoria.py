from pathlib import Path
from types import SimpleNamespace
import json,pytest
from services.asignacion_tenant_auditoria import aprobar_propuesta,rechazar_propuesta,aplicar_propuesta

def obj(**kw):return SimpleNamespace(**kw)
class Sesion:
 def __init__(self):self.commits=0
 def commit(self):self.commits+=1
def propuesta(estado="preparada"):
 a=obj(id=4,organizacion_id=None);e={"estado":"asignable","organizacion_propuesta_id":7};return obj(id=2,auditoria=a,auditoria_id=4,organizacion_propuesta_id=7,estado=estado,evidencia_json=json.dumps(e),aprobado_por=None,aplicado_por=None,motivo_rechazo=None)
def test_aprueba_sin_modificar_auditoria():
 p=propuesta();s=Sesion();aprobar_propuesta(p,usuario=obj(username="admin"),db_session=s);assert p.estado=="aprobada" and p.auditoria.organizacion_id is None and s.commits==1
def test_aplica_solo_aprobada_y_confirmada():
 p=propuesta("aprobada");s=Sesion();aplicar_propuesta(p,confirmacion="ASIGNAR TENANT",usuario=obj(username="admin"),db_session=s);assert p.estado=="aplicada" and p.auditoria.organizacion_id==7 and s.commits==1
def test_rechaza_confirmacion_estado_y_evidencia_invalidos():
 with pytest.raises(ValueError):aplicar_propuesta(propuesta("aprobada"),confirmacion="SI",usuario=obj(username="a"),db_session=Sesion())
 with pytest.raises(ValueError):aplicar_propuesta(propuesta(),confirmacion="ASIGNAR TENANT",usuario=obj(username="a"),db_session=Sesion())
 p=propuesta("aprobada");p.evidencia_json='{"estado":"ambiguo","organizacion_propuesta_id":7}'
 with pytest.raises(ValueError):aplicar_propuesta(p,confirmacion="ASIGNAR TENANT",usuario=obj(username="a"),db_session=Sesion())
def test_rechazo_conserva_auditoria():
 p=propuesta();s=Sesion();rechazar_propuesta(p,motivo="Ambigua",usuario=obj(username="admin"),db_session=s);assert p.estado=="rechazada" and p.auditoria.organizacion_id is None
def test_modelo_y_rutas_declaran_flujo_auditable():
 m=Path("models/asignacion_tenant_auditoria.py").read_text(encoding="utf-8");a=Path("app.py").read_text(encoding="utf-8");h=Path("templates/admin_auditoria_legacy.html").read_text(encoding="utf-8");assert "UniqueConstraint" in m and "evidencia_json" in m;assert "obtener_propuestas_tenant(" in a and "preparar_propuestas(" in a and "aplicar_propuesta(" in a;assert "ASIGNAR TENANT" in h
def test_servicio_sin_borrado_o_conexiones():
 s=Path("services/asignacion_tenant_auditoria.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("delete(","requests","urlopen","http://","https://"))
