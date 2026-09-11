import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.preparacion_pedidos_tienda_nube import exportar_plan, preparar_plan


def fila(order_id="100", sku="PP6040H", bloqueos=None, store="STORE-1"):
    return {"order_id": order_id, "numero": "N100", "identidad": f"{store}:{order_id}", "store_id": store, "total_centavos": 120000, "estado_pago": "paid", "telefono_presente": True, "bloqueos": bloqueos or [], "productos": [{"sku": sku, "nombre": "Parrilla", "cantidad": 1}]}


def lote(filas=None, estado="aprobado", tenant=2):
    return SimpleNamespace(id=7, organizacion_id=tenant, unidad_negocio_id=3, tienda_nube_cuenta_id=8, store_id_snapshot="STORE-1", huella_documento="a"*64, estado=estado, puede_ejecutar=False, evidencia_json=json.dumps({"resultados": filas if filas is not None else [fila()]}))


def producto(sku="PP6040H", tenant=2, id=5):
    return SimpleNamespace(id=id, organizacion_id=tenant, sku=sku)


def pedido(order_id="100", tenant=2, id=9):
    return SimpleNamespace(id=id, organizacion_id=tenant, unidad_negocio_id=3, tn_order_id=order_id)


def plan(lote_obj=None, pedidos=None, productos=None):
    return preparar_plan(lote_obj or lote(), pedidos or [], productos if productos is not None else [producto()], organizacion_id=2, unidad_negocio_id=3)


def test_prepara_alta_simulada_con_producto_tenant():
    resultado=plan(); item=resultado["filas"][0]
    assert item["estado"]=="preparado" and item["crearia_pedido"]
    assert item["items"][0]["producto_id"]==5
    assert resultado["escrituras"]==resultado["acciones_externas"]==0 and not resultado["puede_aplicar"]


def test_detecta_pedido_existente_sin_duplicarlo():
    resultado=plan(pedidos=[pedido()]); item=resultado["filas"][0]
    assert item["estado"]=="existente" and item["pedido_existente_id"]==9 and not item["crearia_pedido"]


def test_bloquea_sku_inexistente_y_ambiguo():
    inexistente=plan(productos=[])["filas"][0]
    ambiguo=plan(productos=[producto(id=1),producto(id=2)])["filas"][0]
    assert "sku_inexistente" in inexistente["bloqueos"]
    assert "sku_ambiguo" in ambiguo["bloqueos"]


def test_bloquea_store_inconsistente_y_bloqueos_de_origen():
    resultado=plan(lote([fila(store="OTRO",bloqueos=["pago_no_confirmado"])]))["filas"][0]
    assert set(resultado["bloqueos"])=={"pago_no_confirmado","store_inconsistente"}


def test_excluye_pedidos_y_productos_ajenos_al_tenant():
    resultado=plan(pedidos=[pedido(tenant=9)],productos=[producto(tenant=9)])["filas"][0]
    assert "pedido_existente" not in resultado["bloqueos"] and "sku_inexistente" in resultado["bloqueos"]


def test_exige_lote_aprobado_del_tenant_y_sin_ejecucion():
    for item in (lote(estado="preparado"),lote(tenant=9)):
        with pytest.raises(ValueError): plan(item)
    item=lote();item.puede_ejecutar=True
    with pytest.raises(ValueError): plan(item)


def test_firma_y_exportacion_json_son_estables_utf8():
    primero=plan();segundo=plan()
    assert primero["firma_plan"]==segundo["firma_plan"]
    exportado=json.loads(exportar_plan(primero).getvalue().decode("utf-8"))
    assert exportado["firma_plan"]==primero["firma_plan"]


def test_panel_y_ruta_son_de_solo_lectura():
    ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html=Path("templates/admin_preparacion_pedidos_tienda_nube.html").read_text(encoding="utf-8")
    bloque=ruta.split("def preparar_pedidos_tienda_nube_comercial",1)[1].split("\n    @blueprint.route",1)[0]
    assert "db.session" not in bloque and "organizacion_id=organizacion.id" in bloque
    assert "Pedido.query.filter_by" in bloque and 'value="exportar_plan"' in html
    assert "Aplicación bloqueada" in html


def test_servicio_no_importa_modelos_transporte_ni_persistencia():
    fuente=Path("services/preparacion_pedidos_tienda_nube.py").read_text(encoding="utf-8").lower()
    prohibidos=("from models","db.session","requests","urlopen","access_token","client_secret","http://","https://",".commit(",".add(","pedido(")
    assert not any(texto in fuente for texto in prohibidos)
