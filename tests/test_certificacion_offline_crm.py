from pathlib import Path
from types import SimpleNamespace
import json
from services.certificacion_offline_crm import certificar_crm,exportar_certificacion
def objetos():
 m=SimpleNamespace(estado="prueba");u=SimpleNamespace(id=1,organizacion_id=7);e=SimpleNamespace(id=2,organizacion_id=7);c=SimpleNamespace(id=3,organizacion_id=7,codigo="C-1",unidad_negocio_id=1,estado="cliente",documento="20",email="a@b.com",telefono="1");i=SimpleNamespace(id=4,organizacion_id=7,cliente_crm_id=3,canal="whatsapp",identificador_externo="5491");o=SimpleNamespace(id=5,organizacion_id=7,cliente_crm_id=3,unidad_negocio_id=1,etapa_crm_id=2,estado="abierta",probabilidad=50,importe_estimado_centavos=100);a=SimpleNamespace(id=6,organizacion_id=7,cliente_crm_id=3,oportunidad_crm_id=5,estado="pendiente",fecha_completada=None);return m,u,e,c,i,o,a
def ejecutar(**kw):
 m,u,e,c,i,o,a=objetos();base=dict(organizacion_id=7,modulo=m,unidades=[u],etapas=[e],clientes=[c],identidades=[i],oportunidades=[o],actividades=[a]);base.update(kw);return certificar_crm(**base)
def test_certificacion_limpia_y_desconectada():
 r=ejecutar();assert r["aprobada"] and r["resumen"]["clientes"]==1 and r["controles"]["automatizaciones"] is False and r["controles"]["mensajes_enviados"]==0
def test_detecta_contactos_duplicados_e_invalidos():
 m,u,e,c,i,o,a=objetos();d=SimpleNamespace(**c.__dict__);d.id=9;d.codigo="C-2";d.email="mal";r=ejecutar(clientes=[c,d]);assert {"documento_duplicado","telefono_duplicado","email_invalido"}<={x["codigo"] for x in r["hallazgos"]}
def test_detecta_identidad_asignada_a_dos_clientes():
 m,u,e,c,i,o,a=objetos();d=SimpleNamespace(**c.__dict__);d.id=9;d.codigo="C-2";d.documento=d.email=d.telefono=None;j=SimpleNamespace(**i.__dict__);j.id=10;j.cliente_crm_id=9;r=ejecutar(clientes=[c,d],identidades=[i,j]);assert not r["controles"]["identidades_unicas"]
def test_detecta_relaciones_ajenas():
 m,u,e,c,i,o,a=objetos();o.cliente_crm_id=99;a.oportunidad_crm_id=99;r=ejecutar(oportunidades=[o],actividades=[a]);assert {"oportunidad_huerfana","actividad_huerfana"}<={x["codigo"] for x in r["hallazgos"]}
def test_detecta_economia_y_actividad_invalidas():
 m,u,e,c,i,o,a=objetos();o.probabilidad=120;a.estado="completada";r=ejecutar(oportunidades=[o],actividades=[a]);assert {"economia_oportunidad_invalida","actividad_completada_sin_fecha"}<={x["codigo"] for x in r["hallazgos"]}
def test_excluye_otro_tenant_y_huella_es_estable():
 m,u,e,c,i,o,a=objetos();c.organizacion_id=99;a=ejecutar(clientes=[c],identidades=[],oportunidades=[],actividades=[]);b=ejecutar(clientes=[c],identidades=[],oportunidades=[],actividades=[]);assert a["resumen"]["clientes"]==0 and a["huella"]==b["huella"]
def test_exportacion_utf8():
 r=ejecutar();assert json.loads(exportar_certificacion(r).read())["modo"]=="offline"
def test_panel_y_servicio_no_tocan_produccion():
 ruta=Path("modules/admin/crm/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_certificacion_crm_offline.html").read_text(encoding="utf-8");s=Path("services/certificacion_offline_crm.py").read_text(encoding="utf-8").lower();assert ".query" not in ruta and "no envía mensajes" in html and not any(x in s for x in ("pedido.query","requests","urlopen","db.session","commit(","wa_enviar","ml_sync","tn_sync"))
