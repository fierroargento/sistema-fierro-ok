from datetime import date
from types import SimpleNamespace

from services.cuentas_pagar_productivas import (
    actualizar_estado, resumen_vencimientos, saldo_obligacion,
)


def obligacion(importe, pagos, vencimiento, estado="pendiente"):
    return SimpleNamespace(
        importe_centavos=importe,
        pagos=[SimpleNamespace(importe_centavos=p) for p in pagos],
        fecha_vencimiento=vencimiento, estado=estado,
    )


def test_varios_pagos_a_cuenta_actualizan_saldo_y_estado():
    item = obligacion(10000, [2500, 3000], date(2026, 8, 10))
    assert saldo_obligacion(item) == 4500
    assert actualizar_estado(item) == "parcial"
    item.pagos.append(SimpleNamespace(importe_centavos=4500))
    assert actualizar_estado(item) == "pagada"


def test_alertas_separan_vencidas_y_proximas():
    vencida = obligacion(100, [], date(2026, 8, 10))
    proxima = obligacion(100, [], date(2026, 8, 15))
    resumen = resumen_vencimientos([vencida, proxima], hoy=date(2026, 8, 12))
    assert resumen == {"vencidas": [vencida], "proximas": [proxima]}
