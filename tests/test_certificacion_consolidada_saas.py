import hashlib,io,json
from pathlib import Path
import pytest
from services.certificacion_consolidada_saas import consolidar_certificaciones,exportar_expediente

def firmado(componente,org=7,aprobado=True):
 resumen={"hallazgos":0};controles={"acciones_externas":0}
 if componente=="estructura":resumen["vinculos_canales"]=1;controles["modulos_activados"]=0
 elif componente=="accesos":resumen["administradores_activos"]=1;controles["credenciales_expuestas"]=0
 elif componente=="inventario":resumen["existencias"]=1;controles["publicaciones_canales"]=0
 elif componente=="crm":resumen["clientes"]=1;controles["automatizaciones"]=False
 elif componente=="facturacion":resumen["entidades_fiscales"]=1;controles["emision_real"]=0
 d={"organizacion_id":org,"modo":"offline","aprobado":aprobado,"resumen":resumen,"controles":controles};d["huella_control"]=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return io.BytesIO(json.dumps(d).encode())
def completos():return [firmado(x) for x in ("estructura","accesos","inventario","crm","facturacion")]
def test_consolida_cinco_componentes_y_firma():
 r=consolidar_certificaciones(completos(),organizacion_id=7);assert r["aprobada"] and r["resumen"]["faltantes"]==0 and len(r["huella_expediente"])==64
def test_detecta_faltantes_y_no_aprobados():
 r=consolidar_certificaciones([firmado("estructura",aprobado=False)],organizacion_id=7);assert not r["aprobada"] and r["resumen"]["hallazgos"]==5
def test_rechaza_otro_tenant_y_firma_alterada():
 with pytest.raises(ValueError,match="otro tenant"):consolidar_certificaciones([firmado("estructura",org=9)],organizacion_id=7)
 d=json.loads(firmado("estructura").read());d["aprobado"]=False
 with pytest.raises(ValueError,match="huella digital"):consolidar_certificaciones([io.BytesIO(json.dumps(d).encode())],organizacion_id=7)
def test_detecta_componente_duplicado():
 r=consolidar_certificaciones(completos()+[firmado("crm")],organizacion_id=7);assert "componente_duplicado" in {x["codigo"] for x in r["hallazgos"]}
def test_limites_y_utf8():
 with pytest.raises(ValueError):consolidar_certificaciones([],organizacion_id=7)
 assert json.loads(exportar_expediente(consolidar_certificaciones(completos(),organizacion_id=7)).read())["modo"]=="offline"
def test_servicio_y_panel_sin_persistencia():
 s=Path("services/certificacion_consolidada_saas.py").read_text(encoding="utf-8").lower();r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_certificacion_consolidada_saas.html").read_text(encoding="utf-8");assert not any(x in s for x in ("db.session","commit(","rollback(","requests","urlopen","http://","https://","delete("));assert "consolidar_certificaciones(" in r and "No persiste documentos" in h
