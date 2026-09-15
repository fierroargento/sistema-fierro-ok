from pathlib import Path
from types import SimpleNamespace
import json
from services.control_integral_estructura_saas import controlar_estructura,exportar_control

def obj(**kw):return SimpleNamespace(**kw)
def base(**cambios):
 u=obj(id=1,organizacion_id=7,codigo="hogar",activa=True);s=obj(id=2,organizacion_id=7,codigo="central",activa=True,es_principal=True);e=obj(id=3,organizacion_id=7,codigo="fiscal",cuit="20301234567",activa=True,facturacion_habilitada=False);c=obj(id=4,organizacion_id=7,codigo="general",unidad_negocio_id=1);m=obj(id=5,organizacion_id=7,codigo="crm",estado="prueba");v=obj(id=6,organizacion_id=7,unidad_negocio_id=1,catalogo_id=4,sucursal_operativa_id=2,entidad_fiscal_id=3,mercado_libre_cuenta_id=8,tienda_nube_cuenta_id=None,whatsapp_phone_number_id=None);d=dict(unidades=[u],sucursales=[s],entidades_fiscales=[e],catalogos=[c],productos=[],modulos=[m],vinculos_canales=[v]);d.update(cambios);return controlar_estructura(organizacion=obj(id=7,activa=True),datos=d)
def test_control_limpio_y_solo_lectura():
 r=base();assert r["aprobado"] and r["controles"]["escrituras"]==0 and r["resumen"]["vinculos_canales"]==1
def test_detecta_codigos_y_sucursal_principal():
 u=obj(id=1,organizacion_id=7,codigo="",activa=True);r=base(unidades=[u,obj(id=9,organizacion_id=7,codigo="",activa=True)],sucursales=[]);assert {"codigo_duplicado","tenant_activo_sin_unidad"}.intersection({x["codigo"] for x in r["hallazgos"]})
def test_detecta_relaciones_y_cuenta_ambiguas():
 v=obj(id=6,organizacion_id=7,unidad_negocio_id=99,catalogo_id=99,sucursal_operativa_id=99,entidad_fiscal_id=99,mercado_libre_cuenta_id=8,tienda_nube_cuenta_id=9,whatsapp_phone_number_id=None);r=base(vinculos_canales=[v]);assert len(r["hallazgos"])>=5
def test_detecta_entidad_y_modulo_invalidos():
 e=obj(id=3,organizacion_id=7,codigo="f",cuit="123",activa=False,facturacion_habilitada=True);m=obj(id=5,organizacion_id=7,codigo="crm",estado="online");r=base(entidades_fiscales=[e],modulos=[m]);assert {"cuit_invalido_o_duplicado","facturacion_sobre_entidad_inactiva","estado_modulo_invalido"}<={x["codigo"] for x in r["hallazgos"]}
def test_excluye_otro_tenant_y_firma_estable():
 x=obj(id=9,organizacion_id=99,codigo="");a=base(modulos=[x]);b=base(modulos=[x]);assert a["resumen"]["modulos"]==0 and a["huella_control"]==b["huella_control"]
def test_exporta_utf8():assert json.loads(exportar_control(base()).read())["modo"]=="solo_lectura"
def test_panel_y_servicio_no_operan():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");s=Path("services/control_integral_estructura_saas.py").read_text(encoding="utf-8").lower();h=Path("templates/admin_control_estructura_saas.html").read_text(encoding="utf-8");assert "controlar_estructura(" in r;assert not any(x in s for x in ("db.session","commit(","rollback(","pedido.query","requests","urlopen","ml_sync","tn_sync","wa_enviar","delete("));assert "No activa módulos, conecta cuentas, modifica pedidos ni emite facturas" in h
