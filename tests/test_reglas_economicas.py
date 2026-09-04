from decimal import Decimal
from pathlib import Path

from services.reglas_economicas import (
    calcular_piso_economico,
    calcular_pisos_regla,
    clave_alcance,
    resolver_regla_vigente,
)


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def test_piso_sobre_costo_resuelve_impuesto_sobre_liquidacion():
    resultado = calcular_piso_economico(
        10000, impuesto_pct=21, metodo_impuesto="sobre_liquidacion",
        utilidad_pct=20, metodo_utilidad="sobre_costo",
        redondeo_centavos=10,
    )
    assert resultado == {
        "costo_centavos": 10000,
        "piso_liquidacion_centavos": 15190,
        "impuesto_centavos": 3190,
        "utilidad_centavos": 2000,
    }


def test_piso_admite_utilidad_e_impuesto_sobre_liquidacion():
    resultado = calcular_piso_economico(
        10000, impuesto_pct=21, metodo_impuesto="sobre_liquidacion",
        utilidad_pct=20, metodo_utilidad="sobre_liquidacion",
        redondeo_centavos=10,
    )
    assert resultado["piso_liquidacion_centavos"] == 16950
    assert resultado["utilidad_centavos"] >= 3390


def test_regla_calcula_minimo_y_objetivo_sin_costos_del_canal():
    regla = Obj(
        impuesto_pct=21, metodo_impuesto="sobre_liquidacion",
        utilidad_minima_pct=15, utilidad_objetivo_pct=25,
        metodo_utilidad="sobre_costo", incremento_redondeo_centavos=100,
    )
    pisos = calcular_pisos_regla(10000, regla)
    assert pisos["minimo"]["piso_liquidacion_centavos"] == 14600
    assert pisos["objetivo"]["piso_liquidacion_centavos"] == 15900


def test_excepcion_mas_especifica_gana_y_producto_es_por_unidad():
    reglas = [
        Obj(vigente=True, clave_alcance="organizacion"),
        Obj(vigente=True, clave_alcance="unidad:2"),
        Obj(vigente=True, clave_alcance="catalogo:7"),
        Obj(vigente=True, clave_alcance="producto:2:9"),
    ]
    assert resolver_regla_vigente(
        reglas, unidad_negocio_id=2, catalogo_id=7, producto_id=9,
    ).clave_alcance == "producto:2:9"
    assert clave_alcance(
        "producto", unidad_negocio_id=2, producto_id=9,
    ) == "producto:2:9"


def test_modelo_panel_y_bootstrap_exponen_reglas_saas_desconectadas():
    modelo = Path("models/regla_economica.py").read_text(encoding="utf-8")
    servicio = Path("services/reglas_economicas.py").read_text(encoding="utf-8")
    template = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    assert "class ReglaEconomicaVersion" in modelo
    assert 'value="crear_regla_economica"' in template
    assert "Prioridad: producto → catálogo → unidad → organización" in template
    assert "Liquidación mínima" in template
    assert '"ReglaEconomicaVersion"' in app
    assert '"ReglaEconomicaVersion"' in bootstrap
    for prohibido in (
        "requests", "OAuth", "Webhook", "MercadoLibre", "comision_pct",
        "cargo_fijo_centavos", "flete_venta_centavos",
    ):
        assert prohibido not in servicio


def test_porcentajes_imposibles_son_rechazados():
    try:
        calcular_piso_economico(
            10000, impuesto_pct=60, metodo_impuesto="sobre_liquidacion",
            utilidad_pct=40, metodo_utilidad="sobre_liquidacion",
        )
    except ValueError as error:
        assert "sumar menos de 100" in str(error)
    else:
        raise AssertionError("Se aceptó una liquidación matemáticamente imposible.")
