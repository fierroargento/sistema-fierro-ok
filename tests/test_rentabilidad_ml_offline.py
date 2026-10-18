from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO, ESCENARIOS, escenario_rentabilidad
from services.rentabilidad_ml_offline import analizar_rentabilidad, _repartir


def documento(clave="simple"):
    return escenario_rentabilidad(clave, organizacion_id=1, unidad_negocio_id=3)[0]


def analizar(d):
    return analizar_rentabilidad(d, organizacion_id=1, unidad_negocio_id=3, cuenta_codigo=CUENTA_ENSAYO)


def test_resultado_simple_distinto_del_neto_y_del_recargo():
    r = analizar(documento())
    assert r["totales"]["resultado_centavos"] == 320000
    assert r["totales"]["margen_pct"] == "32.00"
    assert r["liquidacion"]["observada_centavos"] == 750000
    assert r["totales"]["diferencia_resultado_centavos"] == 0
    assert r["estado"] == "alcance_declarado_completo"


def test_pack_conserva_cuatro_ordenes_y_dos_lineas_del_mismo_sku():
    r = analizar(documento("pack"))
    assert len(r["lineas"]) == 4
    assert len({x["order_id"] for x in r["lineas"]}) == 4
    assert sum(x["cantidad"] for x in r["lineas"]) == 5
    assert [x["ingreso_centavos"] for x in r["lineas"] if x["sku"] == "DEMO-SKU-A"] == [1000000, 900000]
    assert r["totales"]["resultado_centavos"] == 2040000
    envios = [c for x in r["lineas"] for c in x["componentes"] if c["concepto"] == "envio"]
    assert sum(x["importe_centavos"] for x in envios) == 400000
    assert all(x["asignacion"] == "proporcional_al_ingreso" for x in envios)


@pytest.mark.parametrize("importe,pesos", [(1, {"a": 1, "b": 1, "c": 1}), (101, {"a": 3, "b": 7}), (13, {"a": 0, "b": 0})])
def test_reparto_conserva_centavos_y_es_estable(importe, pesos):
    a = _repartir(importe, list(pesos), pesos)
    b = _repartir(importe, list(reversed(pesos)), pesos)
    assert a == b and sum(a.values()) == importe


def test_dos_fuentes_del_mismo_hecho_no_duplican_comision():
    r = analizar(documento("neto"))
    assert r["fuentes_duplicadas_no_sumadas"] == 1
    assert r["totales"]["resultado_centavos"] == 320000
    assert r["liquidacion"]["observada_centavos"] == 750000


def test_dos_fuentes_incompatibles_se_rechazan():
    d = documento("neto"); d["eventos"][-1]["importe_centavos"] += 1
    with pytest.raises(ValueError, match="incompatibles"):
        analizar(d)


def test_fuentes_ausentes_y_estimaciones_no_se_convierten_en_cero_confirmado():
    r = analizar(documento("faltantes"))
    assert r["estado"] == "parcial" and "publicidad" in r["faltantes"]
    d = documento(); d["eventos"][0]["estado"] = "estimado"
    assert analizar(d)["estado"] == "parcial"


def test_costo_ausente_no_toma_cero_ni_dato_vigente_ajeno():
    d = documento("sin_costo"); d["costo_actual_centavos"] = 1
    r = analizar(d)
    assert r["estado"] == "no_calculable"
    assert r["totales"]["resultado_centavos"] is None
    assert r["totales"]["margen_pct"] is None


def test_costo_historico_no_cambia_por_costo_actual_y_no_muta_entrada():
    d = documento(); copia = deepcopy(d)
    antes = analizar(d); d["costo_actual_centavos"] = 900000
    assert analizar(d)["totales"] == antes["totales"]
    d.pop("costo_actual_centavos")
    assert d == copia


@pytest.mark.parametrize("cambio", [{"vigente_desde": "2026-10-21T00:00:00Z"}, {"vigente_hasta": "2026-10-20T00:00:00Z"}])
def test_version_costo_fuera_fecha_rechazada(cambio):
    d = documento(); d["lineas"][0]["costo_snapshot"].update(cambio)
    with pytest.raises(ValueError, match="fecha de venta"):
        analizar(d)


def test_embalaje_ya_incluido_no_se_descuenta_dos_veces():
    d = documento(); c = d["lineas"][0]["costo_snapshot"]
    c["unitario_centavos"] = 430000; c["incluye_embalaje"] = True
    with pytest.raises(ValueError, match="embalaje ya integra"):
        analizar(d)
    d["eventos"] = [e for e in d["eventos"] if e["tipo"] != "embalaje"]
    d["gastos_locales_previstos_centavos"] = 0
    assert analizar(d)["totales"]["resultado_centavos"] == 320000


def test_neto_incompatible_con_detalle_queda_parcial():
    d = documento(); d["eventos"][-1]["importe_centavos"] -= 50000
    r = analizar(d)
    assert r["estado"] == "parcial"
    assert r["liquidacion"]["diferencia_detalle_centavos"] == -50000


def test_faltan_gastos_locales_previstos_no_presupone_cero():
    d = documento(); del d["gastos_locales_previstos_centavos"]
    r = analizar(d)
    assert r["estado"] == "parcial" and r["totales"]["resultado_previsto_centavos"] is None


def test_cobertura_de_comision_sin_detalle_no_aprueba():
    d = documento(); d["eventos"] = [e for e in d["eventos"] if e["tipo"] != "comision"]
    assert "Detalle incompleto de comision" in analizar(d)["faltantes"]


def test_devolucion_parcial_conserva_costo_y_no_repite_venta():
    r = analizar(documento("devolucion"))
    assert r["totales"]["ingreso_economico_centavos"] == 750000
    assert r["totales"]["costo_centavos"] == 400000
    assert r["totales"]["resultado_centavos"] == 70000
    assert r["liquidacion"]["estado"] == "devolucion_parcial"


def test_mayorista_usa_precio_efectivo_sin_reaplicar_descuentos():
    r = analizar(documento("mayorista"))
    assert r["lineas"][0]["cantidad"] == 5
    assert r["totales"]["ingreso_centavos"] == 4275000
    assert r["totales"]["resultado_centavos"] == 1283750


def test_anulacion_sin_reintegro_no_certifica_resultado_completo():
    d = documento(); d["estado_venta"] = "cancelada"
    assert "Resolución económica de la anulación o devolución" in analizar(d)["faltantes"]


def test_retencion_sin_clasificar_no_es_gasto_ni_resultado_completo():
    d = documento(); r = deepcopy(d["eventos"][0])
    r.update(hecho_id="retencion", tipo="retencion", importe_centavos=10000)
    d["eventos"].append(r); d["eventos"][-2]["importe_centavos"] -= 10000
    salida = analizar(d)
    assert salida["totales"]["resultado_centavos"] == 320000
    assert salida["estado"] == "parcial"
    assert any("retención" in f for f in salida["faltantes"])


@pytest.mark.parametrize("clave", ["faltantes", "sin_costo"])
def test_no_ofrece_precio_objetivo_con_fuentes_faltantes(clave):
    _, meta = escenario_rentabilidad(clave, organizacion_id=1, unidad_negocio_id=3)
    assert meta["precio_objetivo_centavos"] is None


@pytest.mark.parametrize("campo,valor", [("organizacion_id", 2), ("unidad_negocio_id", 9), ("cuenta_codigo", "otra"), ("moneda", "USD"), ("version", True)])
def test_contexto_ajeno_y_moneda_incompatible_bloqueados(campo, valor):
    d = documento(); d[campo] = valor
    with pytest.raises(ValueError):
        analizar(d)


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), Decimal("NaN"), True, -1, 10**20, "1000"])
def test_importes_invalidos_no_generan_resultado(valor):
    d = documento(); d["lineas"][0]["precio_unitario_centavos"] = valor
    with pytest.raises(ValueError):
        analizar(d)


def test_linea_duplicada_y_alcance_ajeno_rechazados():
    d = documento(); d["lineas"].append(deepcopy(d["lineas"][0]))
    with pytest.raises(ValueError, match="repetida"):
        analizar(d)
    d = documento(); d["eventos"][0]["lineas"] = ["linea-ajena"]
    with pytest.raises(ValueError, match="propias"):
        analizar(d)


def test_neto_cero_explicito_es_diferente_de_falta_cobro():
    d = documento(); d["eventos"][-1]["importe_centavos"] = 0; d["eventos"][-1]["estado"] = "cero_confirmado"
    assert analizar(d)["liquidacion"]["observada_centavos"] == 0
    d["eventos"].pop()
    assert analizar(d)["liquidacion"]["observada_centavos"] is None


def test_cobro_bruto_menos_detalle_equivale_a_liquidacion_neta():
    d = documento(); bruto = deepcopy(d["eventos"].pop())
    bruto.update(hecho_id="cobro-bruto", tipo="pago_bruto", importe_centavos=1000000)
    for e in d["eventos"]:
        e["incluido_en_neto"] = False
    d["eventos"].append(bruto)
    r = analizar(d)
    assert r["estado"] == "alcance_declarado_completo"
    assert r["liquidacion"]["observada_centavos"] == 750000
    assert r["totales"]["resultado_centavos"] == 320000


def test_resultado_negativo_se_preserva_como_perdida():
    d = documento(); d["lineas"][0]["costo_snapshot"]["unitario_centavos"] = 900000
    r = analizar(d)
    assert r["totales"]["resultado_centavos"] == -180000
    assert r["totales"]["margen_pct"] == "-18.00"


def test_prevision_negativa_por_cargos_mayores_al_ingreso_no_se_recorta():
    d = documento(); d["lineas"][0]["previsto"]["liquidacion_centavos"] = -10000
    r = analizar(d)
    assert r["liquidacion"]["prevista_centavos"] == -10000
    assert r["totales"]["resultado_previsto_centavos"] == -440000


def test_ingreso_cero_no_produce_division_ni_margen_inventado():
    d = documento(); f = d["lineas"][0]
    f["precio_unitario_centavos"] = 0; f["costo_snapshot"]["unitario_centavos"] = 0
    f["previsto"]["liquidacion_centavos"] = 0; d["gastos_locales_previstos_centavos"] = 0
    for e in d["eventos"]:
        e["importe_centavos"] = 0; e["estado"] = "cero_confirmado"
    r = analizar(d)
    assert r["totales"]["resultado_centavos"] == 0
    assert r["totales"]["margen_pct"] is None


def test_un_neto_no_suprime_bruto_de_otras_lineas():
    d = documento("pack")
    neto = d["eventos"][-1]; neto["lineas"] = ["linea-1"]
    # Un bruto de todo el pack no se puede mezclar con un neto de una sola línea.
    bruto = deepcopy(neto); bruto.update(hecho_id="bruto", tipo="pago_bruto", lineas=[x["linea_id"] for x in d["lineas"]])
    d["eventos"].append(bruto)
    with pytest.raises(ValueError, match="mezcla líneas"):
        analizar(d)


@pytest.mark.parametrize("clave", ESCENARIOS)
def test_ejemplos_reproducibles_huella_y_efectos_cero(clave):
    d = documento(clave); r = analizar(d)
    assert r == analizar(d)
    h = r.pop("huella_rentabilidad")
    assert h == sha256(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert r["controles"] == {"persistencia": False, "conexiones_externas": 0, "stock": 0, "pagos": 0, "publicaciones": 0}
