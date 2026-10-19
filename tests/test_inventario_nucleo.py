from pathlib import Path
from types import SimpleNamespace

import pytest

from services.inventario_nucleo import (
    aplicar_movimiento,
    cantidad_publicable,
    inventario_habilita_sincronizacion,
    stock_disponible,
)


def existencia(**cambios):
    datos = {
        "stock_actual": 10,
        "stock_reservado": 2,
        "control_activo": False,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_calcula_stock_disponible():
    assert stock_disponible(
        existencia()
    ) == 8


def test_ingreso_aumenta_stock():
    stock = existencia()

    resultado = aplicar_movimiento(
        stock,
        "ingreso",
        5,
    )

    assert stock.stock_actual == 15
    assert stock.stock_reservado == 2
    assert (
        resultado["stock_actual_anterior"]
        == 10
    )
    assert resultado["stock_actual_nuevo"] == 15


def test_reserva_no_supera_disponible():
    stock = existencia()

    with pytest.raises(
        ValueError,
        match="suficiente",
    ):
        aplicar_movimiento(
            stock,
            "reserva",
            9,
        )


def test_egreso_respeta_reservas():
    stock = existencia()

    with pytest.raises(
        ValueError,
        match="suficiente",
    ):
        aplicar_movimiento(
            stock,
            "egreso",
            9,
        )


def test_liberacion_no_supera_reserva():
    stock = existencia()

    with pytest.raises(
        ValueError,
        match="más stock",
    ):
        aplicar_movimiento(
            stock,
            "liberacion",
            3,
        )


def test_ajuste_no_deja_stock_negativo():
    stock = existencia()

    with pytest.raises(
        ValueError,
        match="no puede ser negativo",
    ):
        aplicar_movimiento(
            stock,
            "ajuste",
            -11,
        )


def test_publicacion_requiere_controles_activos():
    stock = existencia(
        control_activo=False
    )
    politica = SimpleNamespace(
        activa=True,
        permite_sin_stock=False,
        umbral_publicacion=2,
        maximo_publicable=None,
    )

    assert cantidad_publicable(
        stock,
        politica,
    ) == 0


def test_publicable_descuenta_reserva_y_umbral():
    stock = existencia(
        stock_actual=20,
        stock_reservado=3,
        control_activo=True,
    )
    politica = SimpleNamespace(
        activa=True,
        permite_sin_stock=False,
        umbral_publicacion=2,
        maximo_publicable=10,
    )

    assert cantidad_publicable(
        stock,
        politica,
    ) == 10


def test_modulo_no_sincroniza_canales():
    modulo = SimpleNamespace(
        estado="activo"
    )

    assert (
        inventario_habilita_sincronizacion(
            modulo
        )
        is False
    )


def test_modelos_no_referencian_pedidos():
    archivos = [
        "models/existencia_sucursal.py",
        "models/movimiento_inventario.py",
        "models/politica_disponibilidad_catalogo.py",
    ]

    for archivo in archivos:
        contenido = Path(archivo).read_text(
            encoding="utf-8"
        )
        assert "Pedido" not in contenido


def test_runtime_no_importa_inventario():
    archivos = [
        "services/ml_importacion.py",
        "services/canal_manager.py",
        "modules/whatsapp/runtime.py",
        "modules/automation/manager.py",
    ]

    for archivo in archivos:
        contenido = Path(archivo).read_text(
            encoding="utf-8-sig"
        )
        assert "ExistenciaSucursal" not in contenido
        assert "MovimientoInventario" not in contenido


def test_stock_negativo_explicito_egreso_ajuste_y_recuperacion():
    e = existencia(stock_actual=0, stock_reservado=0)
    aplicar_movimiento(e, 'egreso', 2, permitir_stock_negativo=True)
    assert e.stock_actual == -2
    aplicar_movimiento(e, 'ajuste', -3, permitir_stock_negativo=True)
    assert e.stock_actual == -5
    aplicar_movimiento(e, 'ingreso', 6, permitir_stock_negativo=True)
    assert e.stock_actual == 1


def test_negativo_no_relaja_reservas_bloqueos_ni_publicable():
    e = existencia(stock_actual=-2, stock_reservado=0, stock_bloqueado=0, control_activo=True)
    with pytest.raises(ValueError, match='suficiente'):
        aplicar_movimiento(e, 'reserva', 1, permitir_stock_negativo=True)
    assert e.stock_actual == -2 and e.stock_reservado == 0
    politica = SimpleNamespace(activa=True, permite_sin_stock=False, umbral_publicacion=0, maximo_publicable=None)
    assert cantidad_publicable(e, politica) == 0
    e.stock_bloqueado = -1
    with pytest.raises(ValueError, match='bloqueado no puede ser negativo'):
        aplicar_movimiento(e, 'ingreso', 3, permitir_stock_negativo=True)
    assert e.stock_actual == -2


def test_ajuste_rechazado_preserva_saldo_en_memoria():
    e = existencia(stock_actual=2, stock_reservado=0)
    with pytest.raises(ValueError, match='no puede ser negativo'):
        aplicar_movimiento(e, 'ajuste', -3)
    assert e.stock_actual == 2
