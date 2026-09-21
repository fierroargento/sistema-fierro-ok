import json
from pathlib import Path
from services.snapshots_corte_dux import construir_snapshot_fierro,plantilla_snapshot_dux,exportar
class O:
 def __init__(s,**k):s.__dict__.update(k)
def test_snapshot_agrega_stock_precio_y_estado():
 p=O(id=1,sku=" abc ");i=O(producto_id=1,activo=True,precio_lista_centavos=None,precio_centavos=1250);stocks=[O(producto_id=1,stock_actual=2),O(producto_id=1,stock_actual=3)]
 r=construir_snapshot_fierro(organizacion_id=7,unidad_negocio_id=9,productos=[p],inclusiones=[i],existencias=stocks,pedidos=[]);assert r["productos"]==[{"sku":"ABC","stock":5,"precio_centavos":1250,"activo":True}]
def test_snapshot_solo_incluye_pedidos_abiertos():
 pedidos=[O(id=1,id_venta="A",ml_pack_id=None,tn_order_id=None,estado="Cargando Pedido"),O(id=2,id_venta="B",ml_pack_id=None,tn_order_id=None,estado="Finalizado")]
 r=construir_snapshot_fierro(organizacion_id=7,unidad_negocio_id=9,productos=[],inclusiones=[],existencias=[],pedidos=pedidos);assert r["pedidos_abiertos"]==[{"id_externo":"A"}]
def test_producto_sin_precio_activo_permanece_inactivo():
 r=construir_snapshot_fierro(organizacion_id=7,unidad_negocio_id=9,productos=[O(id=1,sku="X")],inclusiones=[],existencias=[],pedidos=[]);assert r["productos"][0]["precio_centavos"]==0 and not r["productos"][0]["activo"]
def test_snapshot_firmado_reproducible_y_sin_impacto():
 kw=dict(organizacion_id=7,unidad_negocio_id=9,productos=[],inclusiones=[],existencias=[],pedidos=[]);a=construir_snapshot_fierro(**kw);b=construir_snapshot_fierro(**kw);assert a["huella_snapshot"]==b["huella_snapshot"]==json.load(exportar(a))["huella_snapshot"] and not any(a["controles"].values())
def test_plantilla_dux_comparte_contrato():
 p=plantilla_snapshot_dux();assert set(p)>={"productos","pedidos_abiertos"} and set(p["productos"][0])=={"sku","stock","precio_centavos","activo"}
def test_ruta_es_tenant_y_solo_lectura():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");s=Path("services/snapshots_corte_dux.py").read_text(encoding="utf-8").lower();assert 'route("/admin/estructura/snapshot-corte/<origen>")' in r and 'filter_by(organizacion_id=organizacion.id' in r
 for x in ("db.session","commit(","requests.","urlopen","http://","https://"):assert x not in s
