from pathlib import Path
from types import SimpleNamespace
import json

from services.certificacion_integral_inventario import certificar_inventario,exportar_certificacion


def obj(**kw): return SimpleNamespace(**kw)


def base(**cambios):
    datos=dict(sucursales=[obj(id=1,organizacion_id=7)],items_inventario=[obj(id=2,organizacion_id=7,sku="SKU-1")],existencias=[obj(id=3,organizacion_id=7,sucursal_operativa_id=1,item_inventario_id=2,stock_actual=10,stock_reservado=2,stock_bloqueado=1,stock_transito=0,stock_minimo=0,stock_maximo=20)],movimientos=[],reservas=[],transferencias=[],conteos=[],eventos_inventario_pedidos=[],eventos_canal_inventario=[],propuestas_publicacion_inventario=[],combinaciones_faltantes=[],automatizacion_pedidos=obj(id=4,organizacion_id=7,estado="desactivado"));datos.update(cambios);return certificar_inventario(organizacion_id=7,datos=datos)


def test_certificacion_limpia_y_sin_efectos():
    resultado=base();assert resultado["aprobado"] and resultado["controles"]=={"aislamiento_tenant":True,"automatizacion_pedidos":False,"publicaciones_canales":0,"reservas_creadas":0,"movimientos_creados":0,"acciones_externas":0,"escrituras":0}


def test_detecta_sku_y_existencia_duplicados():
    items=[obj(id=2,organizacion_id=7,sku="A"),obj(id=4,organizacion_id=7,sku="a")];e=obj(id=5,organizacion_id=7,sucursal_operativa_id=1,item_inventario_id=2,stock_actual=1,stock_reservado=0,stock_bloqueado=0,stock_transito=0,stock_minimo=0,stock_maximo=2);r=base(items_inventario=items,existencias=[e,obj(**{**e.__dict__,"id":6})]);assert {x["codigo"] for x in r["hallazgos"]}>={"sku_duplicado","existencia_duplicada"}


def test_detecta_cantidades_y_relaciones_invalidas():
    e=obj(id=3,organizacion_id=7,sucursal_operativa_id=99,item_inventario_id=88,stock_actual=2,stock_reservado=3,stock_bloqueado=0,stock_transito=0,stock_minimo=5,stock_maximo=1);r=base(existencias=[e]);codigos={x["codigo"] for x in r["hallazgos"]};assert {"sucursal_ajena","item_ajeno","cantidades_inconsistentes","limites_invertidos"}<=codigos


def test_detecta_reserva_y_transferencia_inconsistentes():
    reserva=obj(id=5,organizacion_id=7,existencia_sucursal_id=99,clave_idempotencia="",cantidad=0);transferencia=obj(id=6,organizacion_id=7,existencia_origen_id=3,existencia_destino_id=3,cantidad_solicitada=1,cantidad_despachada=2,cantidad_recibida=3);r=base(reservas=[reserva],transferencias=[transferencia]);assert len(r["hallazgos"])>=5


def test_bloquea_automatizacion_y_propuesta_ejecutable():
    propuesta=obj(id=8,organizacion_id=7,puede_ejecutar=True);r=base(automatizacion_pedidos=obj(id=4,organizacion_id=7,estado="activo"),propuestas_publicacion_inventario=[propuesta]);assert {"automatizacion_activa","propuesta_ejecutable"}<={x["codigo"] for x in r["hallazgos"]}


def test_excluye_otro_tenant_y_huella_estable():
    item=obj(id=9,organizacion_id=99,sku="");a=base(items_inventario=[item]);b=base(items_inventario=[item]);assert a["resumen"]["items_inventario"]==0 and a["huella_control"]==b["huella_control"]


def test_exporta_utf8():
    assert json.loads(exportar_certificacion(base()).read())["modo"]=="offline"


def test_panel_y_servicio_son_solo_lectura():
    ruta=Path("modules/admin/inventario/routes.py").read_text(encoding="utf-8");servicio=Path("services/certificacion_integral_inventario.py").read_text(encoding="utf-8").lower();html=Path("templates/admin_certificacion_inventario.html").read_text(encoding="utf-8");assert ".query" not in ruta and "certificar_inventario(" in ruta;assert not any(x in servicio for x in ("pedido.query","requests","urlopen","db.session","commit(","rollback(","ml_sync","tn_sync","wa_enviar","delete("));assert "No reserva, mueve ni publica stock" in html
