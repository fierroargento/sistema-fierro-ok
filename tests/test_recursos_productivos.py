from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.recursos_productivos import calcular_componentes_recurso
from services.fuentes_costo_productivo import calcular_tarifa_laboral


def _empleado(nombre, costo, horas):
    version = SimpleNamespace(
        vigente=True,
        moneda="ARS",
        sueldo_base_centavos=costo,
        cargas_sociales_centavos=0,
        adicionales_centavos=0,
        otros_costos_centavos=0,
        horas_mensuales=horas,
        horas_productivas=horas,
    )
    return SimpleNamespace(nombre=nombre, versiones_costo=[version])


def test_tarifa_de_recurso_es_ponderada_y_separa_tiempo_indirecto():
    recurso = SimpleNamespace(
        nombre="Equipo Herrería",
        tipo_registro="recurso",
        porcentaje_indirecto=Decimal("10"),
        miembros_recurso=[
            SimpleNamespace(
                empleado=_empleado("Ana", 15_000_000, Decimal("100")),
                porcentaje_dedicacion=Decimal("100"),
            ),
            SimpleNamespace(
                empleado=_empleado("Bruno", 10_000_000, Decimal("50")),
                porcentaje_dedicacion=Decimal("50"),
            ),
        ],
    )

    valores = calcular_componentes_recurso(recurso)

    assert valores["costo_directo_centavos"] == 20_000_000
    assert valores["costo_indirecto_centavos"] == 2_000_000
    assert valores["horas_productivas"] == Decimal("125")
    assert valores["otros_costos_centavos"] == 2_000_000
    assert sum(
        valores[campo] for campo in (
            "sueldo_base_centavos", "cargas_sociales_centavos",
            "adicionales_centavos", "otros_costos_centavos",
        )
    ) / float(valores["horas_productivas"]) == 176_000


def test_recurso_sin_integrantes_no_inventa_una_tarifa():
    recurso = SimpleNamespace(
        nombre="Equipo vacío", tipo_registro="recurso",
        porcentaje_indirecto=0, miembros_recurso=[],
    )

    with pytest.raises(ValueError, match="no tiene empleados"):
        calcular_componentes_recurso(recurso)


def test_porcentaje_general_se_calcula_sobre_sueldo_base():
    tarifa = calcular_tarifa_laboral(
        sueldo_base_centavos=100_000_000,
        porcentaje_cargas=Decimal("25"),
        adicionales_centavos=10_000_000,
        otros_costos_centavos=5_000_000,
        horas_mensuales=Decimal("176"),
        horas_productivas=Decimal("160"),
    )

    assert tarifa["cargas_sociales_centavos"] == 25_000_000
    assert tarifa["porcentaje_cargas"] == Decimal("25")
    assert tarifa["costo_mensual_total_centavos"] == 140_000_000
    assert tarifa["costo_hora_productiva_centavos"] == 875_000


def test_recursos_permanecen_aislados_de_app_y_tienen_importacion_masiva():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path("services/recursos_productivos.py").read_text(encoding="utf-8")
    importador = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")

    assert "def calcular_componentes_recurso" in servicio
    assert "calcular_componentes_recurso" not in app
    assert '"recursos": {' in importador
    assert "Importar recursos" in panel
    assert "configurar_porcentaje_costo_laboral" in panel
    assert "Estimación general del costo laboral" in panel


def test_configuracion_general_es_historica_por_unidad_y_no_engrosa_app():
    app = Path("app.py").read_text(encoding="utf-8")
    modelo = Path("models/fuentes_costo_productivo.py").read_text(encoding="utf-8")
    servicio = Path("services/configuracion_costo_laboral.py").read_text(encoding="utf-8")
    migracion = Path("services/migraciones_saas.py").read_text(encoding="utf-8")

    assert "class ConfiguracionCostoLaboralVersion" in modelo
    assert "usa_porcentaje_general" in modelo
    assert "def registrar_configuracion" in servicio
    assert "def recalcular_empleados_generales" in servicio
    assert "configuracion_costo_laboral_version" not in app.lower()
    assert "ADD COLUMN porcentaje_cargas" in migracion
