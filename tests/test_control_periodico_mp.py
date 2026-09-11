import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from services.control_periodico_mp import construir_control_periodico, exportar_control_periodico


def cierre(id, diferencia, estado="cerrado", tenant=2, unidad=3, certificada=True, dias=0):
    fila={"esperado":1000,"real":1000+diferencia,"diferencia":diferencia}
    snapshot={"filas":[fila],"ventas_ids":[id],"movimientos_ids":[id+10],"gestiones_ids":[]}
    return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=unidad,estado=estado,fecha_creacion=datetime(2026,1,10)-timedelta(days=dias),snapshot_json=json.dumps(snapshot),certificacion_json=json.dumps({"aprobada":certificada}))


def test_control_filtra_tenant_y_ordena_periodos():
    reporte=construir_control_periodico([cierre(1,20,dias=2),cierre(2,0,dias=1),cierre(9,999,tenant=8)],organizacion_id=2,unidad_negocio_id=3)
    assert [fila["id"] for fila in reporte["filas"]]==[2,1]
    assert reporte["resumen"]["cierres"]==2


def test_compara_diferencia_con_cierre_anterior():
    reporte=construir_control_periodico([cierre(1,20,dias=2),cierre(2,50,dias=1)],organizacion_id=2,unidad_negocio_id=3)
    assert reporte["filas"][0]["variacion_centavos"]==30
    assert reporte["filas"][1]["variacion_centavos"] is None


def test_resume_abiertos_bloqueos_y_descuadres():
    reporte=construir_control_periodico([cierre(1,0),cierre(2,-10,"revision",certificada=False)],organizacion_id=2,unidad_negocio_id=3)
    assert reporte["resumen"]=={"cierres":2,"abiertos":1,"cerrados":1,"descuadrados":1,"bloqueados":1,"acciones_externas":0}
    assert all(fila["puede_ejecutar"] is False for fila in reporte["filas"])


def test_exporta_csv_utf8_y_json_en_memoria():
    reporte=construir_control_periodico([cierre(1,0)],organizacion_id=2,unidad_negocio_id=3)
    csv_archivo,csv_tipo,csv_nombre=exportar_control_periodico(reporte,"csv")
    json_archivo,json_tipo,json_nombre=exportar_control_periodico(reporte,"json")
    assert csv_archivo.getvalue().startswith(b"\xef\xbb\xbf") and csv_tipo=="text/csv" and csv_nombre.endswith(".csv")
    assert json.loads(json_archivo.getvalue())["resumen"]["acciones_externas"]==0 and json_tipo=="application/json" and json_nombre.endswith(".json")


def test_panel_expone_control_y_descargas():
    ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html=Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    assert "construir_control_periodico" in ruta and "control_periodico_mp=control_periodico_mp" in ruta
    assert 'value="exportar_control_periodico_mp_csv"' in html and 'value="exportar_control_periodico_mp_json"' in html


def test_contrato_desconectado():
    fuente=Path("services/control_periodico_mp.py").read_text(encoding="utf-8").lower()
    assert not any(texto in fuente for texto in ("requests", "urlopen", "access_token", "client_secret", "http://", "https://", "db.session"))
    assert '"puede_ejecutar": false' in fuente
