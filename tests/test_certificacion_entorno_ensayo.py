import hashlib
from pathlib import Path
from services.certificacion_entorno_ensayo import certificar
def base():
 url="postgresql://ensayo:clave@host/ensayo";return {"SISTEMA_FIERRO_ENTORNO":"staging","MODO_LABORATORIO_DESCONECTADO":"true","DATABASE_URL":url,"BASE_PRODUCTIVA_HUELLA_SHA256":hashlib.sha256(b"postgresql://produccion:secreta@host/prod").hexdigest(),"CONEXIONES_EXTERNAS_HABILITADAS":"false","EFECTOS_EXTERNOS_HABILITADOS":"false","WEBHOOKS_HABILITADOS":"false","SCHEDULER_ENABLED":"false","BOOTSTRAP_BASE_DATOS_HABILITADO":"false"}
def test_aprueba_staging_forzado_con_base_separada():
 r=certificar(base());assert r["aprobado"] and r["base_separada"] and r["laboratorio_forzado"] and len(r["huella_base_ensayo"])==64
def test_rechaza_base_productiva_reutilizada():
 e=base();e["BASE_PRODUCTIVA_HUELLA_SHA256"]=hashlib.sha256(e["DATABASE_URL"].encode()).hexdigest();r=certificar(e);assert "base_productiva_reutilizada" in {x["codigo"] for x in r["hallazgos"]}
def test_rechaza_entorno_candado_huella_y_llaves_inseguros():
 e=base();e.update(SISTEMA_FIERRO_ENTORNO="produccion",MODO_LABORATORIO_DESCONECTADO="false",BASE_PRODUCTIVA_HUELLA_SHA256="",SCHEDULER_ENABLED="true");c={x["codigo"] for x in certificar(e)["hallazgos"]};assert {"entorno_no_staging","candado_no_forzado","huella_productiva_ausente","llaves_maestras_activas"}<=c
def test_no_expone_url_ni_hace_conexiones():
 e=base();r=certificar(e);assert e["DATABASE_URL"] not in repr(r) and not any(r["controles"].values());s=Path("services/certificacion_entorno_ensayo.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("requests.","urlopen","create_engine","db.session","connect("))
def test_panel_muestra_candado_superior():
 h=Path("templates/admin_integraciones.html").read_text(encoding="utf-8");assert "laboratorio_forzado" in h and "Candado superior activo" in h
