from pathlib import Path
import subprocess
import sys

import pytest

from services.costos_productos import (
    calcular_subtotal_detalle,
    normalizar_moneda,
    preparar_detalles,
)


def test_calculo_usa_decimal_y_merma():
    assert calcular_subtotal_detalle(
        cantidad="2.5",
        costo_unitario_centavos=1000,
        porcentaje_merma="10",
    ) == 2750


def test_normaliza_moneda():
    assert normalizar_moneda(" ars ") == "ARS"

    with pytest.raises(
        ValueError,
        match="tres letras",
    ):
        normalizar_moneda("peso")


def test_rechaza_ordenes_repetidos():
    detalles = [
        {
            "tipo": "insumo",
            "concepto": "Chapa",
            "cantidad": "1",
            "unidad_medida": "kg",
            "costo_unitario_centavos": 1000,
            "orden": 0,
        },
        {
            "tipo": "mano_obra",
            "concepto": "Soldadura",
            "cantidad": "1",
            "unidad_medida": "hora",
            "costo_unitario_centavos": 2000,
            "orden": 0,
        },
    ]

    with pytest.raises(
        ValueError,
        match="no pueden repetirse",
    ):
        preparar_detalles(detalles)


def test_runtime_sqlite_real():
    resultado = subprocess.run(
        [
            sys.executable,
            "scripts/verificar_costos_runtime.py",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert resultado.returncode == 0, (
        resultado.stdout
        + "\n"
        + resultado.stderr
    )
    assert (
        "Runtime SQLite de costos OK"
        in resultado.stdout
    )


def test_modelos_definen_constraints_e_indices():
    version = Path(
        "models/costo_producto_version.py"
    ).read_text(encoding="utf-8")
    detalle = Path(
        "models/costo_producto_detalle.py"
    ).read_text(encoding="utf-8")

    assert "db.Numeric(18, 6)" in detalle
    assert "db.Numeric(9, 6)" in detalle
    assert "db.BigInteger" in version
    assert "db.BigInteger" in detalle
    assert (
        "uq_costo_version_vigente_general"
        in version
    )
    assert (
        "uq_costo_version_vigente_unidad"
        in version
    )
    assert (
        "uq_costo_detalle_version_orden"
        in detalle
    )


def test_modulo_no_conecta_consumidores_productivos():
    servicio = Path(
        "services/costos_productos.py"
    ).read_text(encoding="utf-8")
    modelos = (
        Path(
            "models/costo_producto_version.py"
        ).read_text(encoding="utf-8")
        + Path(
            "models/costo_producto_detalle.py"
        ).read_text(encoding="utf-8")
    )

    prohibidos = [
        "MercadoLibre",
        "TiendaNube",
        "Pedido",
        "MovimientoInventario",
        "Webhook",
    ]

    for nombre in prohibidos:
        assert nombre not in servicio
        assert nombre not in modelos


def test_app_solo_registra_modelos_de_costos():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from models.costo_producto_version "
        "import CostoProductoVersion"
        in app
    )
    assert (
        "from models.costo_producto_detalle "
        "import CostoProductoDetalle"
        in app
    )
    assert "services.costos_productos import" not in app
