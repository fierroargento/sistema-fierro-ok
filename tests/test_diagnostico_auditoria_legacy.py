from datetime import datetime
import hashlib,io,json
from pathlib import Path
from types import SimpleNamespace
from services.diagnostico_auditoria_legacy import clasificar_auditorias_legacy,exportar_diagnostico

def obj(**kw):return SimpleNamespace(**kw)
def aud(id,username,org=None):return obj(id=id,username=username,organizacion_id=org,accion="Acción",entidad="pedido",entidad_id="1",fecha=datetime(2026,1,id))
def mem(id,username,org):
 u=obj(username=username);return obj(id=id,usuario=u,usuario_id=id,organizacion_id=org,activa=True)
def test_clasifica_asignable_ambiguo_y_sin_candidato():
 r=clasificar_auditorias_legacy([aud(1,"uno"),aud(2,"dos"),aud(3,"tres")],[mem(1,"uno",7),mem(2,"dos",7),mem(3,"dos",8)]);estados={x["auditoria_id"]:x["estado"] for x in r["auditorias"]};assert estados=={1:"asignable",2:"ambiguo",3:"sin_candidato"} and r["resumen"]["asignaciones_aplicadas"]==0
def test_excluye_registros_ya_identificados():
 r=clasificar_auditorias_legacy([aud(1,"uno",7)],[]);assert r["resumen"]["legacy"]==0
def test_normaliza_username_y_omite_inactivas():
 m=mem(1," Usuario ",7);r=clasificar_auditorias_legacy([aud(1,"usuario")],[m]);assert r["auditorias"][0]["organizacion_propuesta_id"]==7;m.activa=False;assert clasificar_auditorias_legacy([aud(1,"usuario")],[m])["auditorias"][0]["estado"]=="sin_candidato"
def test_huella_verificable_y_exportacion_utf8():
 r=clasificar_auditorias_legacy([aud(1,"uno")],[mem(1,"uno",7)]);firma=r.pop("huella_diagnostico");assert firma==hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();r["huella_diagnostico"]=firma;assert json.loads(exportar_diagnostico(r).read())["auditorias"][0]["accion"]=="Acción"
def test_servicio_no_aplica_backfill():
 s=Path("services/diagnostico_auditoria_legacy.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","rollback(","update(","delete(","requests","urlopen"));assert '"backfill_automatico": false' in s
def test_panel_declara_frontera_y_exporta():
 a=Path("app.py").read_text(encoding="utf-8");h=Path("templates/admin_auditoria_legacy.html").read_text(encoding="utf-8");assert "clasificar_auditorias_legacy(" in a and "No realiza backfill" in h and "Aplicadas: 0" in h
