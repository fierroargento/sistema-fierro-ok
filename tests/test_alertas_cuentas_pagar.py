from datetime import date
from types import SimpleNamespace

from services.alertas_cuentas_pagar import construir_alertas_cuentas_pagar


def obligacion(estado, vencimiento, importe=100, pagos=None):
    return SimpleNamespace(
        estado=estado,
        fecha_vencimiento=vencimiento,
        importe_centavos=importe,
        pagos=[
            SimpleNamespace(importe_centavos=pago, anulado=False)
            for pago in (pagos or [])
        ],
    )


def test_alerta_distingue_vencidas_proximas_y_pagadas():
    alertas = construir_alertas_cuentas_pagar([
        obligacion("pendiente", date(2026, 8, 12)),
        obligacion("parcial", date(2026, 8, 18)),
        obligacion("pagada", date(2026, 8, 10)),
    ], hoy=date(2026, 8, 13), url="/admin/costos#cuentas-pagar")

    assert [alerta["tipo"] for alerta in alertas] == ["roja", "amarilla"]
    assert all(alerta["url"].endswith("#cuentas-pagar") for alerta in alertas)


def test_alerta_no_aparece_sin_pendientes_cercanos():
    alertas = construir_alertas_cuentas_pagar([
        obligacion("pagada", date(2026, 8, 1)),
        obligacion("pendiente", date(2026, 9, 30)),
    ], hoy=date(2026, 8, 13))
    assert alertas == []


def test_alerta_ignora_estado_parcial_si_el_saldo_real_es_cero():
    alertas = construir_alertas_cuentas_pagar([
        obligacion("parcial", date(2026, 8, 1), importe=100, pagos=[100]),
    ], hoy=date(2026, 8, 13))
    assert alertas == []


def test_app_filtra_alertas_por_organizacion_y_rol_admin():
    app = open("app.py", encoding="utf-8").read()
    assert 'if rol == "admin":' in app
    assert "organizacion_id=membresia.organizacion_id" in app
    assert "construir_alertas_cuentas_pagar" in app
