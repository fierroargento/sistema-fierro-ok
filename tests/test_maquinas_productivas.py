from decimal import Decimal
from pathlib import Path

from services.composicion_costo_producto import construir_detalles
from services.maquinas_productivas import calcular_tarifa_maquina


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def test_tarifa_separa_amortizacion_energia_y_mantenimiento():
    tarifa = calcular_tarifa_maquina(
        valor_adquisicion_centavos=120000000,
        valor_residual_centavos=12000000,
        vida_util_horas=12000,
        potencia_kw="1.5",
        factor_carga_pct=80,
        costo_kwh_centavos=20000,
        mantenimiento_mensual_centavos=300000,
        otros_costos_mensuales_centavos=100000,
        horas_productivas_mensuales=100,
    )
    assert tarifa == {
        "amortizacion_hora_centavos": 9000,
        "energia_hora_centavos": 24000,
        "mantenimiento_hora_centavos": 3000,
        "otros_hora_centavos": 1000,
        "costo_hora_centavos": 37000,
        "costo_minuto_centavos": 617,
    }


def test_tarifa_rechaza_residual_superior_y_horas_cero():
    comunes = dict(
        valor_adquisicion_centavos=100,
        valor_residual_centavos=101,
        vida_util_horas=1,
        horas_productivas_mensuales=1,
    )
    try:
        calcular_tarifa_maquina(**comunes)
    except ValueError as error:
        assert "residual" in str(error)
    else:
        raise AssertionError("Se acepto un valor residual imposible.")

    comunes["valor_residual_centavos"] = 0
    comunes["horas_productivas_mensuales"] = 0
    try:
        calcular_tarifa_maquina(**comunes)
    except ValueError as error:
        assert "horas productivas" in str(error)
    else:
        raise AssertionError("Se aceptaron cero horas productivas.")


def test_ficha_incorpora_maquina_como_elaboracion_sin_costo_comercial():
    version = Obj(
        vigente=True, moneda="ARS", costo_minuto_centavos=617,
    )
    maquina = Obj(
        codigo="laser-01", nombre="Laser", versiones_costo=[version],
    )
    perfil = Obj(
        tipo="produccion", organizacion_id=1, unidad_negocio_id=1,
        insumos_costeo=[], operaciones_costeo=[], costos_fijos_costeo=[],
        maquinas_costeo=[Obj(
            maquina=maquina, nombre="Corte laser",
            minutos=Decimal("2.5"), orden=0, observacion=None,
        )],
    )
    detalles = construir_detalles(perfil)
    assert detalles[0]["tipo"] == "elaboracion"
    assert detalles[0]["codigo"] == "laser-01"
    assert detalles[0]["cantidad"] == Decimal("2.5")
    assert detalles[0]["costo_unitario_centavos"] == 617


def test_modelos_nacen_desactivados_y_estan_cableados():
    fuentes = Path("models/fuentes_costo_productivo.py").read_text(encoding="utf-8")
    composicion = Path("models/composicion_costo_producto.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    assert "class MaquinaProductiva" in fuentes
    assert "default=False" in fuentes.split("class MaquinaProductiva", 1)[1].split("class MaquinaCostoVersion", 1)[0]
    assert "class ProductoMaquinaCosteo" in composicion
    for nombre in (
        "MaquinaProductiva", "MaquinaCostoVersion", "ProductoMaquinaCosteo",
    ):
        assert f'"{nombre}"' in app
        assert f'"{nombre}"' in bootstrap


def test_servicio_es_puro_y_no_conecta_canales():
    contenido = Path("services/maquinas_productivas.py").read_text(encoding="utf-8")
    for prohibido in (
        "requests", "OAuth", "Webhook", "MercadoLibre", "db_session",
    ):
        assert prohibido not in contenido


def test_contrato_no_contiene_datos_particulares_de_un_cliente():
    archivos = (
        "models/fuentes_costo_productivo.py",
        "models/composicion_costo_producto.py",
        "services/maquinas_productivas.py",
    )
    contenido = "\n".join(
        Path(ruta).read_text(encoding="utf-8") for ruta in archivos
    )
    for dato_cliente in ("Fierro", "Nautica", "PP6040", "Leetro", "Megalaser"):
        assert dato_cliente not in contenido
