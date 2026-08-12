from datetime import date
from types import SimpleNamespace

from services.cuentas_pagar_productivas import (
    actualizar_estado, resumen_vencimientos, saldo_obligacion,
    ultimo_dia_mes,
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


def test_vencimiento_mes_vencido_respeta_fin_de_mes_y_bisiesto():
    assert ultimo_dia_mes(date(2026, 9, 1)) == date(2026, 9, 30)
    assert ultimo_dia_mes(date(2028, 2, 1)) == date(2028, 2, 29)


def test_obligacion_ajustable_conserva_pagos_y_actualiza_saldo():
    codigo = open("services/cuentas_pagar_productivas.py", encoding="utf-8").read()
    assert "def asegurar_obligacion_ajuste" in codigo
    assert "ajuste_pendiente=True" in codigo
    assert "obligacion.importe_centavos = propuesta.importe_propuesto_centavos" in codigo
    assert "actualizar_estado(obligacion)" in codigo


def test_interfaz_identifica_importe_provisorio_y_pago_a_cuenta():
    plantilla = open("templates/admin_fuentes_costos.html", encoding="utf-8").read()
    assert "Pendiente de ajuste IPC" in plantilla
    assert "importe provisorio" in plantilla
    assert "Registrar pago a cuenta" in plantilla
    assert "Crear obligación manual" in plantilla
