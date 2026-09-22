import hashlib,io,json
from pathlib import Path
import pytest
from services.aceptacion_usuarios_operativos import CASOS,evaluar,exportar,plantilla
def preparacion(estado="preparado_para_decision_humana"):
 d={"organizacion_id":7,"unidad_negocio_id":3,"modo":"evaluacion_preparacion_reemplazo_dux_no_habilitante","estado":estado};d["huella_evaluacion_preparacion"]=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest();return io.BytesIO(json.dumps(d).encode())
def resultados(resultado="aprobado"):
 d=json.loads(plantilla(organizacion_id=7,unidad_negocio_id=3).read());d["participantes"]=["Martín","Ezequiel","Franco"];[(x.update(resultado=resultado,responsable="Usuario de prueba",observacion="Validación documentada")) for x in d["casos"]];return io.BytesIO(json.dumps(d).encode())
def test_aprueba_nueve_areas_y_firma_acta_sin_habilitar():
 r=evaluar(preparacion(),resultados(),organizacion_id=7,unidad_negocio_id=3);assert r["estado"]=="uat_aprobada_para_revision_humana" and r["resumen"]["casos_aprobados"]==len(CASOS) and len(r["huella_acta_uat"])==64;assert r["corte_dux_autorizado"] is False and not any(r["controles"].values())
def test_detecta_preparacion_incompleta_fallos_y_responsables():
 d=json.loads(resultados().read());d["casos"][0].update(resultado="fallido",responsable="",observacion="x");r=evaluar(preparacion("bloqueado_por_brechas"),io.BytesIO(json.dumps(d).encode()),organizacion_id=7,unidad_negocio_id=3);assert {"preparacion_con_brechas","caso_no_aprobado","responsable_faltante","observacion_insuficiente"}<={x["codigo"] for x in r["hallazgos"]}
def test_detecta_casos_faltantes_duplicados_y_pendientes():
 d=json.loads(resultados().read());d["casos"][1]=dict(d["casos"][0]);d["casos"][2]["resultado"]="pendiente";r=evaluar(preparacion(),io.BytesIO(json.dumps(d).encode()),organizacion_id=7,unidad_negocio_id=3);c={x["codigo"] for x in r["hallazgos"]};assert {"caso_duplicado","caso_faltante","resultado_invalido"}<=c
def test_rechaza_firma_y_contexto_ajenos():
 d=json.loads(preparacion().read());d["huella_evaluacion_preparacion"]="x"
 with pytest.raises(ValueError,match="firma"):evaluar(io.BytesIO(json.dumps(d).encode()),resultados(),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otro tenant"):evaluar(preparacion(),resultados(),organizacion_id=8,unidad_negocio_id=3)
def test_exportacion_y_frontera_offline():
 r=evaluar(preparacion(),resultados(),organizacion_id=7,unidad_negocio_id=3);assert json.loads(exportar(r).read())["modo"]=="acta_aceptacion_usuarios_no_habilitante";s=Path("services/aceptacion_usuarios_operativos.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","requests.","urlopen","http://","https://"))
def test_ruta_panel_y_plantilla_disponibles():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_aceptacion_usuarios_operativos.html").read_text(encoding="utf-8");assert "evaluar_uat(" in r and "plantilla_uat(" in r and "resolver_acceso()" in r;assert "nueve áreas" in h
