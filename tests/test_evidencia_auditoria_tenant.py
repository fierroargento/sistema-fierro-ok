from datetime import datetime
import hashlib,json
from pathlib import Path
from types import SimpleNamespace
from services.auditoria_tenant import construir_evidencia_auditoria,exportar_evidencia

def registro(id=1,org=7,accion="Configuró módulo"):
 return SimpleNamespace(id=id,organizacion_id=org,usuario_id=2,username="admin",rol="admin",accion=accion,entidad="modulo",entidad_id="3",detalle="Prueba áéíóú",fecha=datetime(2026,1,2,3,4,5),metodo="POST",path="/admin")
def test_evidencia_filtra_tenant_y_no_incluye_ip():
 r=construir_evidencia_auditoria(7,[registro(),registro(id=2,org=9)]);assert len(r["registros"])==1 and r["registros"][0]["accion"]=="Configuró módulo" and "ip" not in r["registros"][0]
def test_evidencia_es_determinista_y_verificable():
 r=construir_evidencia_auditoria(7,[registro()]);firma=r.pop("huella_evidencia");assert firma==hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def test_exporta_json_utf8():
 r=construir_evidencia_auditoria(7,[registro()]);assert json.loads(exportar_evidencia(r).read())["registros"][0]["detalle"]=="Prueba áéíóú"
def test_exportacion_no_muta_ni_conecta():
 s=Path("services/auditoria_tenant.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","rollback(","requests","urlopen","delete(","update("))
def test_ruta_exige_tenant_admin_y_delega():
 s=Path("app.py").read_text(encoding="utf-8");b=s.split("def admin_auditoria_exportar():",1)[1].split("\n\nfrom modules.admin.integraciones",1)[0];assert "membresia_actual()" in b and 'membresia.rol != "admin"' in b and "construir_evidencia_auditoria(" in b
def test_template_ofrece_descarga():
 assert "admin_auditoria_exportar" in Path("templates/admin_auditoria.html").read_text(encoding="utf-8")
