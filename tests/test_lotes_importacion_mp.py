import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from services.importacion_extracto_mp import exportar_evidencia_lote,resumir_lotes

def lote(id=1,tenant=2,unidad=3,movs=4):return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=unidad,cuenta_codigo="MP",nombre_archivo="mp.csv",huella_documento="a"*64,estado="confirmado",total_filas=movs,movimientos_creados=movs,rechazados=0,evidencia_json=json.dumps({"filas":[]}),puede_ejecutar=False,creado_por_username="admin",fecha_creacion=datetime(2026,1,id))
def test_historial_filtra_tenant_ordena_y_resume():
 r=resumir_lotes([lote(1),lote(2,movs=3),lote(9,tenant=8)],organizacion_id=2,unidad_negocio_id=3)
 assert [x.id for x in r["lotes"]]==[2,1] and r["movimientos"]==7 and r["acciones_externas"]==0
def test_evidencia_preserva_huella_y_bloqueo():
 d=json.loads(exportar_evidencia_lote(lote()).getvalue());assert d["huella_documento"]=="a"*64 and d["puede_ejecutar"] is False
def test_modelo_impide_duplicados_y_ejecucion():
 s=Path("models/lote_importacion_mp.py").read_text(encoding="utf-8").lower();assert "uniqueconstraint" in s and "puede_ejecutar = false" in s
def test_registro_disponible_en_app_y_blueprint():
 app=Path("app.py").read_text(encoding="utf-8");boot=Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8");assert app.count("LoteImportacionMP")>=3 and '"LoteImportacionMP"' in boot
def test_panel_exporta_solo_lote_del_tenant():
 ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8");assert 'request.form.get("accion") == "exportar_lote"' in ruta and "organizacion_id=organizacion.id,unidad_negocio_id=unidad_activa.id" in ruta
def test_contrato_sin_red():
 s=Path("services/importacion_extracto_mp.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("requests","urlopen","access_token","client_secret","http://","https://"))
