import hashlib,io,json
from pathlib import Path
import pytest
from services.expediente_transicion_dux import construir_expediente,exportar
def firmado(campo,**datos):
 datos[campo]=hashlib.sha256(json.dumps(datos,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return io.BytesIO(json.dumps(datos).encode())
def documentos(org=7,bloqueado=False):
 p=firmado("huella_plan",organizacion_id=org,apto_para_ensayo=not bloqueado,autorizacion_corte=False,resumen={"dominios":10});e=firmado("huella_ensayo",organizacion_id=org,aprobado=not bloqueado,autorizacion_corte=False,resumen={"diferencias_productos":0});c=firmado("huella_expediente",organizacion_id=org,aprobada=not bloqueado,resumen={"componentes_identificados":5});return p,e,c
def test_expediente_completo_recomienda_solo_ensayo():
 r=construir_expediente(*documentos(),organizacion_id=7);assert r["decision_recomendada"]=="apto_para_ensayo_controlado" and not r["autorizacion_corte_real"] and not any(r["controles"].values())
def test_bloquea_si_cualquier_evidencia_no_aprueba():
 r=construir_expediente(*documentos(bloqueado=True),organizacion_id=7);assert r["decision_recomendada"]=="bloqueado" and {x["codigo"] for x in r["hallazgos"]}=={"plan_bloqueado","ensayo_con_diferencias","saas_no_certificado"}
def test_rechaza_otro_tenant():
 with pytest.raises(ValueError,match="otro tenant"):construir_expediente(*documentos(org=9),organizacion_id=7)
def test_rechaza_firma_alterada():
 p,e,c=documentos();d=json.loads(p.read());d["apto_para_ensayo"]=False
 with pytest.raises(ValueError,match="firma"):construir_expediente(io.BytesIO(json.dumps(d).encode()),e,c,organizacion_id=7)
def test_firma_final_es_reproducible_y_exportable():
 a=construir_expediente(*documentos(),organizacion_id=7);b=construir_expediente(*documentos(),organizacion_id=7);assert a["huella_expediente_transicion"]==b["huella_expediente_transicion"]==json.load(exportar(a))["huella_expediente_transicion"]
def test_ruta_y_servicio_sin_ejecucion():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");s=Path("services/expediente_transicion_dux.py").read_text(encoding="utf-8").lower();assert 'route("/admin/estructura/expediente-transicion-dux"' in r
 for x in ("db.session","commit(","requests.","urlopen","http://","https://"):assert x not in s
