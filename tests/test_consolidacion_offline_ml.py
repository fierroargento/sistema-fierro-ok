import json
from pathlib import Path
from types import SimpleNamespace

from services.certificacion_offline_mercado_libre import procesar_documento_publicaciones
from services.consolidacion_offline_ml import (
    CONTRATO_EFECTOS, consolidar_snapshot_ml, exportar_consolidacion_json,
)


def control(sku="SKU-1", lista_id=10, precio=130000, piso_minimo=90000, piso_objetivo=100000):
    regla = SimpleNamespace(id=30, lista_precio_id=lista_id, comision_pct="15")
    costo = SimpleNamespace(id=20, producto=SimpleNamespace(sku=sku))
    return {"regla_canal": regla, "costo": costo, "regla": SimpleNamespace(id=40), "inclusion": SimpleNamespace(id=50), "minimo": {"piso_liquidacion_centavos": piso_minimo}, "objetivo": {"piso_liquidacion_centavos": piso_objetivo}, "propuesto": {"precio_final_centavos": precio}, "actual": {"cargo_fijo_centavos": 10000, "envio_centavos": 0}}


def snapshot(**cambios):
    datos = {"id": "MLA-1", "seller_sku": "SKU-1", "price": 1000, "commission_percentage": 15, "fixed_fee": 100, "shipping_cost": 0, "economic_floor": 1}
    datos.update(cambios)
    return procesar_documento_publicaciones(datos, cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)


def test_usa_piso_y_objetivo_del_sistema_no_del_archivo():
    resultado = consolidar_snapshot_ml(snapshot(economic_floor=1), [control()], lista_precio_id=10)
    fila = resultado["resultados"][0]
    assert fila["estado"] == "debajo_del_piso"
    assert fila["piso_minimo_centavos"] == 90000
    assert fila["precio_objetivo_centavos"] == 130000


def test_promocion_ordena_cancelar_antes_de_actualizar():
    resultado = consolidar_snapshot_ml(snapshot(promotion_active=True), [control()], lista_precio_id=10)
    acciones = resultado["resultados"][0]["acciones"]
    assert [item["accion"] for item in acciones] == ["cancelar_promocion_manual", "actualizar_precio_manual"]
    assert acciones[1]["depende_de"] == "cancelar_promocion_manual"
    assert all(item["ejecutada"] is False for item in acciones)


def test_sku_ausente_o_ambiguo_queda_bloqueado():
    ausente = consolidar_snapshot_ml(snapshot(), [control("OTRO")], lista_precio_id=10)
    ambiguo = consolidar_snapshot_ml(snapshot(), [control(), control()], lista_precio_id=10)
    assert ausente["resultados"][0]["bloqueos"] == ["sku_sin_control_interno"]
    assert ambiguo["resultados"][0]["bloqueos"] == ["sku_con_control_interno_ambiguo"]


def test_detecta_desvios_de_comision_cargo_y_envio():
    resultado = consolidar_snapshot_ml(snapshot(commission_percentage=16, fixed_fee=120, shipping_cost=50), [control()], lista_precio_id=10)
    assert len(resultado["resultados"][0]["desvios"]) == 3


def test_evidencia_es_exportable_y_no_aplicable():
    resultado = consolidar_snapshot_ml(snapshot(), [control()], lista_precio_id=10)
    exportado = json.loads(exportar_consolidacion_json(resultado).getvalue().decode("utf-8"))
    assert exportado["firma_evidencia"] == resultado["firma_evidencia"]
    assert resultado["aplicable"] is False
    assert resultado["acciones_externas"] == resultado["escrituras"] == 0
    assert not any(CONTRATO_EFECTOS.values())


def test_ruta_cruza_datos_del_tenant_y_no_habilita_ejecucion():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = rutas.split("def mercado_libre_offline_comercial():", 1)[1].split("@blueprint.route", 1)[0]
    assert "obtener_datos_panel_comercial" in bloque
    assert "organizacion.id" in bloque and "unidad_activa.id" in bloque
    assert "registrar_lote" in bloque
    assert "puede_ejecutar=True" not in bloque


def test_servicio_careece_de_transporte_y_persistencia():
    fuente = Path("services/consolidacion_offline_ml.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "access_token", "client_secret", "http://", "https://"):
        assert prohibido not in fuente
