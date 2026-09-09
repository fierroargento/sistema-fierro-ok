import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from services.lotes_offline_ml import (
    consolidar_lote_secciones, exportar_lote_json,
    plantillas_secciones_zip, preparar_lote_secciones,
)


def archivos(ref="MLA-1"):
    return {
        "precios": json.dumps([{"publicacion_id": ref, "seller_sku": "SKU-1", "price": 1000}]),
        "cargos": json.dumps([{"publicacion_id": ref, "commission_percentage": 15, "fixed_fee": 100}]),
        "envios": json.dumps([{"publicacion_id": ref, "shipping_cost": 0}]),
        "promociones": json.dumps([{"publicacion_id": ref, "promotion_active": True, "original_price": 1100}]),
    }


def control():
    return {"regla_canal": SimpleNamespace(id=3, lista_precio_id=10, comision_pct="15"), "costo": SimpleNamespace(id=4, producto=SimpleNamespace(sku="SKU-1")), "regla": SimpleNamespace(id=5), "inclusion": SimpleNamespace(id=6), "minimo": {"piso_liquidacion_centavos": 90000}, "objetivo": {"piso_liquidacion_centavos": 100000}, "propuesto": {"precio_final_centavos": 130000}, "actual": {"cargo_fijo_centavos": 10000, "envio_centavos": 0}}


def test_une_cuatro_secciones_por_publicacion():
    lote = preparar_lote_secciones(archivos(), cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)
    assert lote["completas"] == lote["referencias"] == 1
    assert lote["errores_lote"] == []
    assert lote["snapshot"]["resultados"][0]["sku"] == "SKU-1"
    assert lote["snapshot"]["resultados"][0]["promocion_activa"] is True


def test_faltante_y_duplicado_se_bloquean_sin_abortarlo_todo():
    datos = archivos()
    datos["envios"] = "[]"
    datos["cargos"] = json.dumps([{"id": "MLA-1", "commission_percentage": 15}, {"id": "MLA-1", "commission_percentage": 15}])
    lote = preparar_lote_secciones(datos, cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)
    assert lote["completas"] == 0
    assert any("duplicada" in error for error in lote["errores_lote"])
    assert any("envios" in error for error in lote["errores_lote"])


def test_firma_de_lote_es_repetible_y_cambia_con_la_fuente():
    primero = preparar_lote_secciones(archivos(), cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)
    segundo = preparar_lote_secciones(archivos(), cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)
    tercero = preparar_lote_secciones(archivos("MLA-2"), cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3)
    assert primero["lote_id"] == segundo["lote_id"]
    assert primero["lote_id"] != tercero["lote_id"]


def test_consolida_con_piso_interno_y_ordena_promocion():
    resultado = consolidar_lote_secciones(archivos(), [control()], cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3, lista_precio_id=10)
    fila = resultado["control"]["resultados"][0]
    assert fila["estado"] == "debajo_del_piso"
    assert [item["accion"] for item in fila["acciones"]] == ["cancelar_promocion_manual", "actualizar_precio_manual"]
    assert resultado["aplicable"] is False


def test_entrega_cuatro_plantillas_separadas_y_exporta_evidencia():
    with ZipFile(plantillas_secciones_zip()) as paquete:
        nombres = set(paquete.namelist())
    assert {"01_precios.csv", "02_cargos.csv", "03_envios.csv", "04_promociones.csv"} <= nombres
    resultado = consolidar_lote_secciones(archivos(), [control()], cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3, lista_precio_id=10)
    assert json.loads(exportar_lote_json(resultado).getvalue().decode("utf-8"))["lote"]["completas"] == 1


def test_panel_tenant_no_persiste_y_ofrece_plantillas():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "/admin/comercial/mercado-libre-offline/plantillas" in rutas
    bloque = rutas.split("def mercado_libre_offline_comercial():", 1)[1].split("@blueprint.route", 1)[0]
    assert "organizacion.id" in bloque and "unidad_activa.id" in bloque
    assert "db.session" not in bloque and ".commit(" not in bloque


def test_servicio_sin_transporte_persistencia_ni_credenciales():
    fuente = Path("services/lotes_offline_ml.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "access_token", "client_secret", "http://", "https://"):
        assert prohibido not in fuente
