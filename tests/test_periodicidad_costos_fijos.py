from decimal import Decimal
from pathlib import Path

import pytest

from services.fuentes_costo_productivo import calcular_equivalente_mensual


def test_patente_anual_se_prorratea_en_doce_meses():
    valor = calcular_equivalente_mensual(
        12000000, naturaleza="fijo", periodicidad="anual",
    )
    assert valor["importe_mensual_centavos"] == 1000000
    assert valor["meses_cobertura"] == Decimal("12")


def test_reparacion_eventual_usa_cobertura_elegida():
    valor = calcular_equivalente_mensual(
        6000000, naturaleza="provision", periodicidad="eventual",
        meses_cobertura="6",
    )
    assert valor["importe_mensual_centavos"] == 1000000
    assert valor["naturaleza"] == "provision"


def test_eventual_exige_meses_de_cobertura():
    with pytest.raises(ValueError, match="meses"):
        calcular_equivalente_mensual(
            100000, naturaleza="variable", periodicidad="eventual",
        )


def test_periodicidad_es_aditiva_y_modular():
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_base_datos.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert "def asegurar_periodicidad_costos_fijos" in migraciones
    assert "asegurar_periodicidad_costos_fijos(" in bootstrap
    assert "def calcular_equivalente_mensual" not in app
    assert "Importe del período" in plantilla
    assert "Meses que cubre" in plantilla


def test_presentacion_separa_bloques_y_muestra_cobertura_solo_en_eventuales():
    plantilla = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    javascript = Path("static/admin_fuentes_costos.js").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")

    assert "Costos indirectos productivos" in plantilla
    assert "fixed-cost-identity" in plantilla
    assert "fixed-cost-valuation" in plantilla
    assert "fixed-cost-complement" in plantilla
    assert "data-cost-periodicity" in plantilla
    assert "data-eventual-months hidden" in plantilla
    assert 'control.value === "eventual"' in javascript
    assert "meses.required = eventual" in javascript
    assert ".fixed-cost-valuation" in estilos
