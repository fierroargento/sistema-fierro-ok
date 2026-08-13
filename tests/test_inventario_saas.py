from pathlib import Path
from types import SimpleNamespace

import pytest

from services.inventario_nucleo import stock_disponible
from services.inventario_saas import (
    diferencia_conteo,
    validar_mismo_tenant,
    validar_transferencia,
)


def test_disponible_descuenta_reserva_y_bloqueo():
    existencia = SimpleNamespace(
        stock_actual=20,
        stock_reservado=4,
        stock_bloqueado=3,
    )
    assert stock_disponible(existencia) == 13


def test_transferencia_exige_mismo_producto_y_distinto_deposito():
    origen = SimpleNamespace(id=1, organizacion_id=8, producto_id=11)
    destino = SimpleNamespace(id=2, organizacion_id=8, producto_id=11)
    transferencia = SimpleNamespace(
        organizacion_id=8,
        origen=origen,
        destino=destino,
        cantidad_solicitada=5,
    )
    assert validar_transferencia(transferencia) is True
    destino.producto_id = 12
    with pytest.raises(ValueError, match="mismo producto"):
        validar_transferencia(transferencia)


def test_operaciones_no_mezclan_tenants():
    with pytest.raises(ValueError, match="otra organización"):
        validar_mismo_tenant(4, SimpleNamespace(organizacion_id=9))


def test_conteo_calcula_diferencia_sin_mutar_stock():
    assert diferencia_conteo(15, 12) == -3
    with pytest.raises(ValueError, match="negativa"):
        diferencia_conteo(15, -1)


def test_modelos_cubren_sku_reservas_transferencias_y_conteos():
    contenido = Path("models/inventario_saas.py").read_text(encoding="utf-8")
    for contrato in (
        "class ItemInventario",
        "class ReservaInventario",
        "clave_idempotencia",
        "class TransferenciaInventario",
        "cantidad_recibida",
        "class ConteoInventario",
        "class ConteoInventarioItem",
    ):
        assert contrato in contenido


def test_canales_siguen_sin_conectarse_al_stock():
    servicio = Path("services/inventario_saas.py").read_text(encoding="utf-8")
    runtime = Path("modules/automation/manager.py").read_text(encoding="utf-8-sig")
    assert "sincroniza canales" in servicio
    assert "crear_reserva(" not in runtime


def test_panel_expone_operaciones_sin_cargar_datos():
    plantilla = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    for titulo in (
        "Reservas por canal",
        "Transferencias entre depósitos",
        "Conteos e inventarios físicos",
        "En tránsito",
    ):
        assert titulo in plantilla
