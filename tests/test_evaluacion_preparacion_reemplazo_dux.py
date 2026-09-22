import hashlib,io,json
from pathlib import Path
import pytest
from services.evaluacion_preparacion_reemplazo_dux import CONTROLES_HUMANOS,evaluar,exportar
def firmado(modo,campo,**extra):
 d={"organizacion_id":7,"unidad_negocio_id":3,"modo":modo,**extra};d[campo]=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest();return io.BytesIO(json.dumps(d).encode())
def archivos():return {"expediente_maestro":firmado("expediente_maestro_preparacion_no_habilitante","huella_expediente_maestro",estado="preparado_para_revision_humana"),"continuidad":firmado("expediente_continuidad_no_ejecutable","huella_expediente_continuidad",estado="apto_para_simulacro_humano"),"aceptacion":firmado("aceptacion_operativa_integral_offline","huella_aceptacion",aprobado=True)}
def confirmaciones():return {codigo:"1" for codigo,_ in CONTROLES_HUMANOS}
def test_consolida_evidencias_y_controles_sin_autorizar_corte():
 r=evaluar(archivos(),confirmaciones(),organizacion_id=7,unidad_negocio_id=3);assert r["estado"]=="preparado_para_decision_humana" and r["resumen"]=={"tecnicos_aprobados":3,"tecnicos_requeridos":3,"humanos_confirmados":6,"humanos_requeridos":6,"brechas":0};assert r["corte_dux_autorizado"] is False and not any(r["controles"].values())
def test_expone_brechas_tecnicas_y_humanas():
 a=archivos();d=json.loads(a["aceptacion"].read());d["aprobado"]=False;d.pop("huella_aceptacion");d["huella_aceptacion"]=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest();a["aceptacion"]=io.BytesIO(json.dumps(d).encode());r=evaluar(a,{},organizacion_id=7,unidad_negocio_id=3);assert r["estado"]=="bloqueado_por_brechas" and r["resumen"]["brechas"]==7
def test_rechaza_firma_contexto_y_modo_invalidos():
 a=archivos();d=json.loads(a["continuidad"].read());d["huella_expediente_continuidad"]="x";a["continuidad"]=io.BytesIO(json.dumps(d).encode())
 with pytest.raises(ValueError,match="firma"):evaluar(a,{},organizacion_id=7,unidad_negocio_id=3)
 a=archivos()
 with pytest.raises(ValueError,match="otro tenant"):evaluar(a,{},organizacion_id=8,unidad_negocio_id=3)
def test_exporta_evaluacion_firmada_utf8():
 r=evaluar(archivos(),confirmaciones(),organizacion_id=7,unidad_negocio_id=3);d=json.loads(exportar(r).read());assert len(d["huella_evaluacion_preparacion"])==64
def test_frontera_sin_ejecucion_ni_conexiones():
 s=Path("services/evaluacion_preparacion_reemplazo_dux.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","requests.","urlopen","http://","https://"));assert '"corte_dux_autorizado": false' in s
def test_ruta_y_panel_disponibles():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_evaluacion_preparacion_reemplazo_dux.html").read_text(encoding="utf-8");assert "evaluar_preparacion_dux(" in r and "resolver_acceso()" in r;assert "nunca autoriza el corte" in h
