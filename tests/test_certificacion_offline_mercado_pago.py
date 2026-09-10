from pathlib import Path
from types import SimpleNamespace

from services.certificacion_offline_mercado_pago import certificar_conciliacion_mp,exportar_certificacion_mp


def venta(**c):
 d=dict(id=1,organizacion_id=2,unidad_negocio_id=3,cuenta_codigo="MP1",referencia_venta="V1",referencia_pago="P1",estado="confirmada",liquidacion_esperada_centavos=1000,piso_unitario_snapshot_centavos=900,cantidad=1,importe_bruto_centavos=1200);d.update(c);return SimpleNamespace(**d)
def mov(**c):
 d=dict(id=2,organizacion_id=2,unidad_negocio_id=3,cuenta_codigo="MP1",referencia_venta="V1",referencia_pago="P1",referencia_movimiento="M1",impacta_saldo=True,estado="confirmado",importe_centavos=1000,direccion="credito");d.update(c);return SimpleNamespace(**d)


def test_escenario_conciliado_aprueba_sin_efectos():
 r=certificar_conciliacion_mp([venta()],[mov()],[],organizacion_id=2,unidad_negocio_id=3)
 assert r["aprobada"] and r["resumen"]["conciliada"]==1 and r["acciones_externas"]==0 and r["escrituras"]==0


def test_bloquea_cruce_tenant_pago_distinto_y_bajo_piso():
 v=venta(organizacion_id=9,liquidacion_esperada_centavos=800)
 r=certificar_conciliacion_mp([v],[mov(referencia_pago="P2")],[],organizacion_id=2,unidad_negocio_id=3)
 assert not r["aprobada"] and len(r["bloqueos"])>=3


def test_advierte_movimiento_huerfano_y_caso_sin_gestion():
 r=certificar_conciliacion_mp([venta()],[mov(referencia_venta="OTRA")],[],organizacion_id=2,unidad_negocio_id=3)
 assert not r["controles"]["movimientos_asociados"] and r["resumen"]["sin_gestion"]==1


def test_exportacion_json_es_utf8():
 dato=exportar_certificacion_mp({"detalle":"conciliación"}).getvalue()
 assert "conciliación" in dato.decode("utf-8")


def test_panel_expone_certificacion_y_descarga():
 ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
 html=Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
 assert "certificar_conciliacion_mp(" in ruta and "exportar_certificacion_mp(" in ruta
 assert 'value="exportar_certificacion_mp"' in html and "Acciones externas" in html


def test_servicio_no_usa_red_credenciales_ni_persistencia():
 fuente=Path("services/certificacion_offline_mercado_pago.py").read_text(encoding="utf-8").lower()
 assert not any(x in fuente for x in ("db.session","requests","urlopen","access_token","client_secret","http://","https://"))
