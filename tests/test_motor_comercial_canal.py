from pathlib import Path

from services.motor_comercial_canal import (
    calcular_precio_minimo_canal,
    cargo_para_precio,
    liquidar_precio,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def regla():
    return Obj(
        comision_pct=10, umbral_envio_centavos=3300000,
        costo_envio_default_centavos=500000,
        incremento_redondeo_centavos=100,
        tramos=[Obj(precio_desde_centavos=0, precio_hasta_centavos=3300000, cargo_fijo_centavos=100000)],
    )


def test_precio_inverso_cubre_piso_con_comision_y_cargo_fijo():
    resultado = calcular_precio_minimo_canal(1000000, regla())
    assert resultado["precio_final_centavos"] == 1222300
    assert resultado["cargo_fijo_centavos"] == 100000
    assert resultado["envio_centavos"] == 0
    assert resultado["liquidacion_centavos"] >= 1000000
    assert resultado["excedente_centavos"] < 100


def test_motor_resuelve_salto_del_umbral_de_envio():
    resultado = calcular_precio_minimo_canal(3000000, regla())
    assert resultado["precio_final_centavos"] == 3888900
    assert resultado["cargo_fijo_centavos"] == 0
    assert resultado["envio_centavos"] == 500000
    assert resultado["liquidacion_centavos"] >= 3000000


def test_costo_envio_real_puede_reemplazar_estimado_sin_mutar_regla():
    politica = regla()
    resultado = calcular_precio_minimo_canal(
        3000000, politica, costo_envio_centavos=700000,
    )
    assert resultado["envio_centavos"] == 700000
    assert politica.costo_envio_default_centavos == 500000


def test_liquidacion_desglosa_todas_las_deducciones():
    politica = regla()
    resultado = liquidar_precio(
        2000000, comision_pct=politica.comision_pct,
        tramos=politica.tramos,
        umbral_envio_centavos=politica.umbral_envio_centavos,
        costo_envio_centavos=politica.costo_envio_default_centavos,
    )
    assert resultado == {
        "precio_final_centavos": 2000000, "comision_centavos": 200000,
        "cargo_fijo_centavos": 100000, "envio_centavos": 0,
        "liquidacion_centavos": 1700000,
    }


def test_tramos_superpuestos_se_rechazan_en_el_calculo():
    tramos = [
        Obj(precio_desde_centavos=0, precio_hasta_centavos=2000, cargo_fijo_centavos=10),
        Obj(precio_desde_centavos=1000, precio_hasta_centavos=3000, cargo_fijo_centavos=20),
    ]
    try: cargo_para_precio(1500, tramos)
    except ValueError as error: assert "superponen" in str(error)
    else: raise AssertionError("Se aceptaron tramos superpuestos.")


def test_contrato_es_generico_y_no_publica_canales():
    motor = Path("services/motor_comercial_canal.py").read_text(encoding="utf-8")
    modelo = Path("models/regla_canal.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert "class ReglaCanalVersion" in modelo
    assert "class ReglaCanalCargoTramo" in modelo
    assert 'value="crear_regla_canal"' in panel
    assert "Simulación sin publicar" in panel
    assert '"ReglaCanalVersion"' in app and '"ReglaCanalCargoTramo"' in app
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "Pedido"):
        assert prohibido not in motor
