from pathlib import Path
from types import SimpleNamespace

from services.certificacion_operativa_ml import certificar_operacion_ml, exportar_certificacion_ml


def lote(i=1, vigente=True): return SimpleNamespace(id=i,organizacion_id=2,unidad_negocio_id=3,puede_ejecutar=False)
def tarea(i=1,estado="preparada",dep=None,eventos=None): return SimpleNamespace(id=i,organizacion_id=2,unidad_negocio_id=3,lote_diagnostico_id=1,puede_ejecutar=False,estado=estado,depende_de=dep,orden=i,comprobante_manual="ticket" if estado=="completada_manual" else None,eventos=eventos or [])


def test_certifica_flujo_sano_sin_efectos():
    r=certificar_operacion_ml([lote()],[tarea()],organizacion_id=2,unidad_negocio_id=3,vigencias={1:True})
    assert r["aprobada"] and r["acciones_externas"]==0 and r["escrituras"]==0


def test_bloquea_tenant_ejecucion_y_obsolescencia():
    t=tarea(); t.organizacion_id=9; t.puede_ejecutar=True
    r=certificar_operacion_ml([lote()],[t],organizacion_id=2,unidad_negocio_id=3,vigencias={1:False})
    assert not r["aprobada"] and len(r["bloqueos"])>=3


def test_bloquea_dependencia_y_comprobante_inconsistentes():
    previa=tarea(2,"aprobada"); actual=tarea(1,"completada_manual",previa); actual.comprobante_manual=""
    r=certificar_operacion_ml([lote()],[previa,actual],organizacion_id=2,unidad_negocio_id=3,vigencias={1:True})
    assert not r["controles"]["dependencias_validas"] and not r["controles"]["comprobantes_validos"]


def test_exporta_json_utf8():
    dato=exportar_certificacion_ml({"aprobada":True,"detalle":"revisión"}).getvalue()
    assert "revisión" in dato.decode("utf-8")


def test_panel_muestra_y_descarga_certificacion():
    ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html=Path("templates/admin_mercado_libre_offline.html").read_text(encoding="utf-8")
    assert "certificar_operacion_ml(" in ruta and "exportar_certificacion_ml(" in ruta
    assert 'value="exportar_certificacion_operativa"' in html
    assert "Acciones externas" in html


def test_servicio_es_solo_lectura_y_desconectado():
    fuente=Path("services/certificacion_operativa_ml.py").read_text(encoding="utf-8").lower()
    assert not any(x in fuente for x in ("db.session", "requests", "urlopen", "access_token", "client_secret", "http://", "https://"))
