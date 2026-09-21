import json
from pathlib import Path
from services.plan_corte_dux import DOMINIOS,construir_plan,exportar_plan

def completos():
 d={"ventana_corte":"2026-12-01 22:00 a 23:00","plan_reversion":"Restaurar DUX como maestro y verificar cada canal.","criterio_exito":"Coincidencia total de stock, precios, pedidos y comprobantes."}
 for x in DOMINIOS:d[x]="on";d[f"responsable_{x}"]="Administrador";d[f"evidencia_{x}"]=f"control_{x}.json"
 return d
def test_plan_completo_solo_habilita_ensayo():
 r=construir_plan(completos(),organizacion_id=7);assert r["apto_para_ensayo"] and not r["autorizacion_corte"] and r["resumen"]=={"dominios":10,"validados":10,"bloqueos":0}
def test_plan_incompleto_enumera_todos_los_bloqueos():
 r=construir_plan({},organizacion_id=7);assert not r["apto_para_ensayo"] and r["resumen"]["bloqueos"]==13
def test_validacion_exige_responsable_y_evidencia():
 r=construir_plan({"catalogo":"on"},organizacion_id=7);codigos={x["codigo"] for x in r["hallazgos"] if x["dominio"]=="catalogo"};assert codigos=={"responsable_faltante","evidencia_faltante"}
def test_firma_es_reproducible_y_exportable():
 a=construir_plan(completos(),organizacion_id=7);b=construir_plan(completos(),organizacion_id=7);assert a["huella_plan"]==b["huella_plan"]==json.load(exportar_plan(a))["huella_plan"]
def test_controles_declaran_cero_impacto():
 assert not any(construir_plan(completos(),organizacion_id=7)["controles"].values())
def test_ruta_y_panel_exponen_plan_no_ejecutable():
 rutas=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_plan_corte_dux.html").read_text(encoding="utf-8");assert 'route("/admin/estructura/plan-corte-dux"' in rutas and "no autoriza el corte" in html
def test_servicio_no_contiene_consumidores_productivos():
 s=Path("services/plan_corte_dux.py").read_text(encoding="utf-8").lower()
 for x in ("db.session","commit(","requests.","urlopen","http://","https://","movimientoinventario(","emitir_factura("):assert x not in s
