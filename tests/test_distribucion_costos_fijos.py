from pathlib import Path
from decimal import Decimal

import pytest

from services.composicion_costo_producto import _factor_productivo_unidad
from services.distribucion_costos_fijos import normalizar_distribucion_costo_fijo


ROOT = Path(__file__).resolve().parents[1]


def test_distribucion_separa_unidad_ubicacion_y_porcion_productiva():
    filas = normalizar_distribucion_costo_fijo([
        {"unidad_negocio_id": "1", "porcentaje_asignacion": "30", "ubicacion_costo": "Taller", "porcentaje_productivo": "100"},
        {"unidad_negocio_id": "2", "porcentaje_asignacion": "70", "ubicacion_costo": "Salón", "porcentaje_productivo": "0"},
    ])
    assert [fila["porcentaje_asignacion"] for fila in filas] == [30, 70]
    assert filas[0]["ubicacion_costo"] == "Taller"
    assert filas[1]["porcentaje_productivo"] == 0


def test_distribucion_debe_sumar_cien():
    with pytest.raises(ValueError, match="100"):
        normalizar_distribucion_costo_fijo([
            {"unidad_negocio_id": 1, "porcentaje_asignacion": 80, "ubicacion_costo": "Taller", "porcentaje_productivo": 100},
        ])


def test_distribucion_de_costos_fijos_permanece_modular():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    servicio = (ROOT / "services" / "distribucion_costos_fijos.py").read_text(encoding="utf-8")
    plantilla = (ROOT / "templates" / "admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert "def registrar_distribucion_costo_fijo" in servicio
    assert "def registrar_distribucion_costo_fijo" not in app
    assert "Distribuir costos indirectos entre unidades" in plantilla
    assert "costo_porcentaje_productivo" in plantilla


def test_factor_productivo_combina_participacion_y_uso_productivo():
    class Registro:
        vigente = True
        unidad_negocio_id = 2
        porcentaje_asignacion = 70
        porcentaje_productivo = 40

    class Costo:
        nombre = "Alquiler"
        distribuciones_versionadas = [Registro()]

    assert _factor_productivo_unidad(Costo(), 2) == Decimal("0.28")


def test_factor_legacy_conserva_costos_anteriores_sin_distribucion():
    class Costo:
        distribuciones_versionadas = []

    assert _factor_productivo_unidad(Costo(), 1) == 1
