from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from services.fuentes_costo_productivo import calcular_tarifa_laboral
from services.recursos_productivos import calcular_componentes_recurso


def test_tarifa_valida_porcentaje_productivo():
    tarifa = calcular_tarifa_laboral(
        sueldo_base_centavos=100_000_000,
        porcentaje_cargas=25,
        horas_mensuales=176,
        horas_productivas=160,
        porcentaje_productivo=25,
    )
    assert tarifa["porcentaje_productivo"] == Decimal("25")
    assert tarifa["costo_mensual_total_centavos"] == 125_000_000


def test_recurso_solo_toma_la_participacion_productiva_del_empleado():
    version = SimpleNamespace(
        vigente=True, moneda="ARS", sueldo_base_centavos=100_000_000,
        cargas_sociales_centavos=25_000_000, adicionales_centavos=0,
        otros_costos_centavos=0, horas_mensuales=176,
        horas_productivas=160, porcentaje_productivo=Decimal("25"),
    )
    empleado = SimpleNamespace(nombre="Encargado", versiones_costo=[version])
    recurso = SimpleNamespace(
        nombre="Supervisión", tipo_registro="recurso", porcentaje_indirecto=0,
        miembros_recurso=[SimpleNamespace(
            empleado=empleado, porcentaje_dedicacion=Decimal("100"),
        )],
    )
    valores = calcular_componentes_recurso(recurso)
    assert valores["costo_directo_centavos"] == 31_250_000
    assert valores["horas_productivas"] == Decimal("40")


def test_distribucion_es_historica_modular_e_importable():
    app = Path("app.py").read_text(encoding="utf-8")
    modelo = Path("models/fuentes_costo_productivo.py").read_text(encoding="utf-8")
    migracion = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    importador = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")

    for campo in ("ubicacion_trabajo", "tipo_funcion", "porcentaje_productivo"):
        assert campo in modelo
        assert f"ADD COLUMN {campo}" in migracion
        assert campo in importador
        assert campo in panel
    assert "porcentaje_productivo" not in app
