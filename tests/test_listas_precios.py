from decimal import Decimal
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from services.listas_precios import (
    calcular_precio_comercial,
    redondear_hacia_arriba,
    validar_alcance_lista,
    validar_organizacion_unidad,
)


def test_calculo_separa_componentes_impuestos_y_margen():
    resultado = calcular_precio_comercial(
        costo_base_centavos=10000,
        flete_venta_centavos=1000,
        cargo_fijo_centavos=500,
        comision_pct="10",
        margen_objetivo_pct="20",
        impuesto_pct="21",
        incremento_redondeo_centavos=100,
    )
    assert resultado["precio_neto_sugerido_centavos"] == 16500
    assert resultado["comision_centavos"] == 1650
    assert resultado["margen_centavos"] == 3350
    assert resultado["margen_pct"] == Decimal("20.303030")
    assert resultado["impuestos_centavos"] == 3465
    assert resultado["precio_final_centavos"] == 19965


def test_precio_elegido_recalcula_margen():
    resultado = calcular_precio_comercial(
        costo_base_centavos=10000,
        comision_pct=10,
        margen_objetivo_pct=20,
        precio_elegido_centavos=20000,
    )
    assert resultado["precio_elegido_centavos"] == 20000
    assert resultado["margen_centavos"] == 8000
    assert resultado["margen_pct"] == Decimal("40.000000")


def test_rechaza_porcentajes_imposibles_y_redondea():
    assert redondear_hacia_arriba(10001, 100) == 10100
    with pytest.raises(ValueError, match="sumar menos"):
        calcular_precio_comercial(
            costo_base_centavos=100,
            comision_pct=50,
            margen_objetivo_pct=50,
        )


def test_valida_tenant_producto_y_moneda():
    catalogo = SimpleNamespace(
        organizacion_id=1, unidad_negocio_id=2,
    )
    inclusion = SimpleNamespace(
        catalogo=catalogo, producto_id=10,
    )
    costo = SimpleNamespace(
        organizacion_id=1, unidad_negocio_id=2,
        producto_id=10, moneda="ARS",
    )
    lista = SimpleNamespace(
        organizacion_id=1, unidad_negocio_id=2, moneda="ARS",
    )
    assert validar_alcance_lista(
        organizacion_id=1, unidad_negocio_id=2,
        catalogo_producto=inclusion, costo_version=costo,
        lista_precio=lista,
    ) is True
    costo.producto_id = 11
    with pytest.raises(ValueError, match="otro producto"):
        validar_alcance_lista(
            organizacion_id=1, unidad_negocio_id=2,
            catalogo_producto=inclusion, costo_version=costo,
            lista_precio=lista,
        )


def test_modelos_registrados_sin_consumidores():
    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path("services/listas_precios.py").read_text(encoding="utf-8")
    for nombre in ("ListaPrecio", "PoliticaComercialLista", "ListaPrecioItem"):
        assert f"import {nombre}" in app
    assert "services.listas_precios import" not in app
    for consumidor in ("MercadoLibre", "TiendaNube", "Pedido", "Webhook"):
        assert consumidor not in servicio


def test_runtime_sqlite_real():
    resultado = subprocess.run(
        [sys.executable, "scripts/verificar_listas_runtime.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "Runtime SQLite de listas OK" in resultado.stdout


def test_rechaza_unidad_ajena_con_sesion_fake():
    organizacion = SimpleNamespace(id=1)
    unidad = SimpleNamespace(id=2, organizacion_id=9)

    class Sesion:
        def get(self, modelo, identificador):
            return organizacion if identificador == 1 else unidad

    with pytest.raises(ValueError, match="no pertenece"):
        validar_organizacion_unidad(
            organizacion_id=1, unidad_negocio_id=2,
            Organizacion=object(), UnidadNegocio=object(),
            db_session=Sesion(),
        )
