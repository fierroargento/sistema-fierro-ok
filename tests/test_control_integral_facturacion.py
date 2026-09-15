from pathlib import Path
from types import SimpleNamespace
import json
from services.control_integral_facturacion import controlar,exportar
def datos():
 m=SimpleNamespace(estado="prueba");e=SimpleNamespace(id=1,organizacion_id=7,activa=True,facturacion_habilitada=True,cuit="30712345678");c=SimpleNamespace(id=2,organizacion_id=7,entidad_fiscal_id=1,estado="prueba");p=SimpleNamespace(id=3,organizacion_id=7,entidad_fiscal_id=1,configuracion_fiscal_id=2,emision_real_habilitada=False);t=SimpleNamespace(id=4,punto_venta_fiscal_id=3);b=SimpleNamespace(id=5,organizacion_id=7,estado="listo",cae=None,numero_autorizado=None);x=SimpleNamespace(id=6,organizacion_id=7,borrador_comprobante_fiscal_id=5,estado="certificado",puede_emitir=False);l=SimpleNamespace(id=7,organizacion_id=7);v=SimpleNamespace(id=8,organizacion_id=7);return m,e,c,p,t,b,x,l,v
def ejecutar(**kw):
 m,e,c,p,t,b,x,l,v=datos();base=dict(organizacion_id=7,modulo=m,entidades=[e],configuraciones=[c],puntos=[p],tipos=[t],borradores=[b],eventos=[v],lotes=[l],expedientes=[x]);base.update(kw);return controlar(**base)
def test_control_aprobado_y_resumen_completo():
 r=ejecutar();assert r["aprobado"] and r["resumen"]=={"entidades":1,"configuraciones":1,"puntos_venta":1,"tipos":1,"borradores":1,"borradores_listos":1,"lotes":1,"expedientes":1,"eventos":1,"hallazgos":0};assert r["controles"]["acciones_externas"]==r["controles"]["escrituras"]==0
def test_detecta_borrador_listo_sin_expediente():assert "listo_sin_expediente" in {x["codigo"] for x in ejecutar(expedientes=[])["hallazgos"]}
def test_detecta_emision_y_autorizacion_inconsistentes():
 m,e,c,p,t,b,x,l,v=datos();p.emision_real_habilitada=True;b.cae="x";r=ejecutar(puntos=[p],borradores=[b]);assert {"emision_real_indebida","autorizacion_inconsistente"}<={x["codigo"] for x in r["hallazgos"]}
def test_detecta_cadena_huerfana():
 m,e,c,p,t,b,x,l,v=datos();c.entidad_fiscal_id=99;p.configuracion_fiscal_id=99;r=ejecutar(configuraciones=[c],puntos=[p]);assert not r["controles"]["integridad_cadena"]
def test_excluye_registros_de_otro_tenant():
 m,e,c,p,t,b,x,l,v=datos();l.organizacion_id=99;x.organizacion_id=99;r=ejecutar(lotes=[l],expedientes=[x],borradores=[]);assert r["resumen"]["lotes"]==r["resumen"]["expedientes"]==0
def test_huella_estable_y_exportacion_utf8():
 a=ejecutar();b=ejecutar();assert a["huella"]==b["huella"] and json.loads(exportar(a).read())["emision_real"] is False
def test_panel_es_solo_lectura_y_sin_query():
 ruta=Path("modules/admin/facturacion/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_control_integral_facturacion.html").read_text(encoding="utf-8");assert ".query" not in ruta and "CONTROL APROBADO" in html and "solo lectura" in html
def test_servicio_sin_transporte_ni_persistencia():
 s=Path("services/control_integral_facturacion.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("requests","urlopen","http://","https://","db.session","commit(","rollback(","access_token","client_secret"))
