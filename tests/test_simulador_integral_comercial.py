from pathlib import Path

from services.simulador_integral_comercial import ESCENARIOS, escenario_predefinido, simular_escenario


def test_cargo_fijo_se_aplica_solo_debajo_del_umbral():
    bajo = simular_escenario(escenario_predefinido("cargo_fijo"))
    alto = simular_escenario(escenario_predefinido("envio"))
    assert bajo["liquidacion_actual"]["cargo_fijo_centavos"] == 143000
    assert bajo["liquidacion_actual"]["envio_centavos"] == 0
    assert alto["liquidacion_actual"]["cargo_fijo_centavos"] == 0
    assert alto["liquidacion_actual"]["envio_centavos"] == 650000


def test_piso_incluye_costo_utilidad_e_impuestos():
    resultado = simular_escenario(escenario_predefinido("promocion"))
    assert resultado["piso"]["piso_liquidacion_centavos"] == 102500
    assert resultado["liquidacion_actual"]["liquidacion_centavos"] == 85000
    assert resultado["cumple_piso"] is False


def test_promocion_bajo_piso_exige_cancelar_antes_de_actualizar():
    resultado = simular_escenario(escenario_predefinido("promocion"))
    assert resultado["accion_propuesta"] == "cancelar_promocion_y_actualizar_precio"
    assert resultado["precio_minimo"]["precio_final_centavos"] > 100000
    assert resultado["precio_base_con_descuento_centavos"] > resultado["precio_minimo"]["precio_final_centavos"]


def test_sin_promocion_propone_solamente_actualizar_precio():
    resultado = simular_escenario(escenario_predefinido("cargo_fijo"))
    assert resultado["cumple_piso"] is False
    assert resultado["accion_propuesta"] == "actualizar_precio"


def test_conciliacion_distingue_pago_parcial_y_devolucion():
    assert simular_escenario(ESCENARIOS["envio"])["estado_conciliacion"] == "pago_parcial"
    assert simular_escenario(ESCENARIOS["devolucion"])["estado_conciliacion"] == "devuelta"


def test_simulador_no_persiste_ni_contiene_conectores():
    servicio = Path("services/simulador_integral_comercial.py").read_text(encoding="utf-8").lower()
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_simulador_integral_comercial.html").read_text(encoding="utf-8")
    assert "/admin/comercial/simulador-integral" in rutas
    assert "Calcula solamente en memoria" in panel
    for prohibido in ("db.session", "requests", "oauth", "webhook", "access_token", "mercadopago", "mercadolibre", "tiendanube"):
        assert prohibido not in servicio


def test_minimo_neto_explicito_no_se_reemplaza_por_porcentajes_del_ejemplo():
    datos=escenario_predefinido('cargo_fijo')
    datos.update(minimo_neto_centavos=2300000,utilidad_pct=99,impuesto_pct=99,
                 publicidad_pct=3,financiacion_pct=2,devoluciones_pct=1,redondeo_centavos=1)
    r=simular_escenario(datos)
    assert r['piso']['piso_liquidacion_centavos']==2300000
    assert r['minimo_neto_explicito'] is True
    assert r['precio_minimo']['liquidacion_centavos']>=2300000
    assert r['precio_minimo']['publicidad_centavos']>0
    assert r['precio_minimo']['financiacion_centavos']>0
    assert r['precio_minimo']['devoluciones_centavos']>0
    assert datos['minimo_neto_centavos']==2300000


def test_minimo_invalido_o_inferior_al_costo_no_se_valida():
    import pytest
    for minimo in (0,100,'NaN','Infinity','1e999999',True,'texto',1800000.5):
        datos=escenario_predefinido('cargo_fijo');datos['minimo_neto_centavos']=minimo
        with pytest.raises(ValueError):simular_escenario(datos)
    datos=escenario_predefinido('cargo_fijo');datos['redondeo_centavos']=0
    with pytest.raises(ValueError,match='paso'):simular_escenario(datos)
