import hashlib,io,json
from pathlib import Path
import pytest
from services.expediente_continuidad_operativa import construir,exportar
def firmado(tipo,d):
 campo={"respaldo":"huella_respaldo","ensayo":"huella_ensayo_restauracion","comparacion":"huella_comparacion"}[tipo];d[campo]=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest();return io.BytesIO(json.dumps(d).encode())
def archivos(org=7,unidad=3):
 respaldo={"organizacion_id":org,"unidad_negocio_id":unidad,"modo":"respaldo_integral_solo_lectura_sin_secretos","respaldo_reconstruible":True};r=firmado("respaldo",respaldo);huella=json.loads(r.getvalue())["huella_respaldo"]
 ensayo=firmado("ensayo",{"organizacion_id":org,"unidad_negocio_id":unidad,"modo":"ensayo_respaldo_restauracion_offline_no_ejecutable","aprobado":True})
 comparacion=firmado("comparacion",{"organizacion_id":org,"unidad_negocio_id":unidad,"modo":"comparacion_respaldos_offline_solo_lectura","estado":"sin_perdidas_detectadas","origenes":{"posterior":{"huella":huella}}})
 return r,ensayo,comparacion
def datos():return {"rpo_minutos":"60","rto_minutos":"120","responsable":"Administrador","custodia":"Copia cifrada fuera del servidor principal","procedimiento_reversion":"Restaurar el respaldo validado en entorno aislado y verificar conteos antes de habilitar.","criterio_validacion":"Conteos, huellas y operaciones criticas coinciden."}
def test_cierra_tres_evidencias_sin_autorizar_ejecucion():
 r=construir(*archivos(),datos(),organizacion_id=7,unidad_negocio_id=3);assert r["estado"]=="apto_para_simulacro_humano" and not r["restauracion_autorizada"] and not r["corte_dux_autorizado"] and len(r["huella_expediente_continuidad"])==64
def test_bloquea_evidencias_y_gobierno_incompletos():
 a,b,c=archivos();d=json.loads(b.read());d["aprobado"]=False;b=firmado("ensayo",{k:v for k,v in d.items() if k!="huella_ensayo_restauracion"});r=construir(a,b,c,{},organizacion_id=7,unidad_negocio_id=3);codigos={x["codigo"] for x in r["hallazgos"]};assert {"ensayo_no_aprobado","rpo_invalido","rto_invalido","responsable_faltante"}<=codigos
def test_rechaza_firmas_tenant_y_unidad():
 a,b,c=archivos();d=json.loads(a.read());d["respaldo_reconstruible"]=False
 with pytest.raises(ValueError,match="firma"):construir(io.BytesIO(json.dumps(d).encode()),b,c,datos(),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otro tenant"):construir(*archivos(org=8),datos(),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otra unidad"):construir(*archivos(unidad=4),datos(),organizacion_id=7,unidad_negocio_id=3)
def test_exporta_utf8_y_frontera():
 r=construir(*archivos(),datos(),organizacion_id=7,unidad_negocio_id=3);assert json.loads(exportar(r).read())["modo"]=="expediente_continuidad_no_ejecutable";s=Path("services/expediente_continuidad_operativa.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","requests.","urlopen","http://","https://"))
def test_ruta_y_panel():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_expediente_continuidad_operativa.html").read_text(encoding="utf-8");assert "construir_expediente_continuidad(" in r and "resolver_acceso()" in r;assert "No restaura bases ni autoriza el corte de DUX" in h

