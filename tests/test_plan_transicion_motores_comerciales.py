import json
from pathlib import Path

from services.plan_transicion_motores_comerciales import (
    construir_plan_transicion,
    exportar_plan_transicion,
)


def control(fila):
    return {"firma_evidencia": "a" * 64, "filas": [fila]}


def fila(**cambios):
    datos = dict(
        lista_id=1, lista="Mercado Libre", bloqueos=[], diferencias=[],
        avisos=[], precios_vigentes=0, retiro_legacy_habilitado=False,
    )
    datos.update(cambios)
    return datos


def test_bloqueos_se_convierten_en_acciones_ordenadas_no_ejecutables():
    plan = construir_plan_transicion(control(fila(
        bloqueos=["multiples_politicas_historicas_vigentes", "solo_motor_historico"],
    )))
    item = plan["listas"][0]
    assert item["fase"] == "resolver_bloqueos"
    assert [accion["orden"] for accion in item["acciones"]] == [1, 2]
    assert all(accion["ejecucion_automatica"] is False for accion in item["acciones"])


def test_diferencias_generan_plan_especifico_de_alineacion():
    plan = construir_plan_transicion(control(fila(
        diferencias=["comision_distinta", "cargo_fijo_distinto"],
    )))
    item = plan["listas"][0]
    assert item["fase"] == "alinear_parametros"
    assert [accion["clave"] for accion in item["acciones"]] == [
        "alinear_comision", "alinear_cargo_fijo",
    ]


def test_validaciones_economicas_y_sombra_permanecen_manuales():
    plan = construir_plan_transicion(control(fila(
        avisos=["margen_historico_debe_resolverse_con_regla_economica"],
        precios_vigentes=8,
        retiro_legacy_habilitado=True,
    )))
    item = plan["listas"][0]
    assert item["fase"] == "validar_resultados"
    assert [accion["clave"] for accion in item["acciones"]] == [
        "validar_regla_economica", "comparar_precios_en_sombra",
    ]
    assert item["retiro_automatico"] is False


def test_lista_sin_pendientes_solo_queda_lista_para_decision_futura():
    plan = construir_plan_transicion(control(fila(retiro_legacy_habilitado=True)))
    item = plan["listas"][0]
    assert item["fase"] == "listo_para_decision"
    assert item["acciones"][0]["clave"] == "autorizar_retiro_en_cambio_futuro"
    assert item["requiere_aprobacion_futura"] is True


def test_exportacion_es_firmada_reproducible_y_sin_efectos():
    primero = construir_plan_transicion(control(fila(retiro_legacy_habilitado=True)))
    segundo = construir_plan_transicion(control(fila(retiro_legacy_habilitado=True)))
    assert primero["firma_plan"] == segundo["firma_plan"]
    salida = json.loads(exportar_plan_transicion(primero).read().decode("utf-8"))
    assert salida == primero
    assert all(primero["garantias"].values())


def test_panel_y_exportacion_respetan_tenant_y_no_escriben():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    consultas = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    servicio = Path("services/plan_transicion_motores_comerciales.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "/admin/comercial/control-motores/plan-transicion" in rutas
    assert '"plan_transicion_motores": plan_transicion_motores' in consultas
    assert "Plan preparatorio por lista" in panel
    assert "no ejecuta retiros ni modifica reglas" in panel
    for prohibido in ("db.session", "requests.", "http://", "https://"):
        assert prohibido not in servicio
