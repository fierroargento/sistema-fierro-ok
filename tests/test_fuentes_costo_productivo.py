from pathlib import Path
import subprocess
import sys

import pytest

from services.fuentes_costo_productivo import calcular_tarifa_laboral


def test_calcula_tarifa_con_horas_productivas():
    tarifa = calcular_tarifa_laboral(
        sueldo_base_centavos=80000000,
        cargas_sociales_centavos=20000000,
        horas_mensuales="176",
        horas_productivas="160",
    )
    assert tarifa["costo_mensual_total_centavos"] == 100000000
    assert tarifa["costo_hora_productiva_centavos"] == 625000
    assert tarifa["costo_minuto_productivo_centavos"] == 10417


def test_rechaza_mas_horas_productivas_que_mensuales():
    with pytest.raises(ValueError, match="no pueden superar"):
        calcular_tarifa_laboral(
            sueldo_base_centavos=100000,
            horas_mensuales="160",
            horas_productivas="180",
        )


def test_runtime_sqlite_fuentes_costo():
    resultado = subprocess.run(
        [sys.executable, "scripts/verificar_fuentes_costo_runtime.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + "\n" + resultado.stderr
    assert "Runtime SQLite de fuentes de costo OK" in resultado.stdout


def test_fuentes_no_conectan_canales_ni_ventas():
    contenido = (
        Path("models/fuentes_costo_productivo.py").read_text(encoding="utf-8")
        + Path("services/fuentes_costo_productivo.py").read_text(encoding="utf-8")
    )
    for prohibido in (
        "MercadoLibre", "TiendaNube", "Pedido", "ListaPrecio",
        "MovimientoInventario", "Webhook",
    ):
        assert prohibido not in contenido


def test_app_solo_registra_modelos_de_fuentes():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "from models.fuentes_costo_productivo import (" in app
    assert "services.fuentes_costo_productivo import" not in app
