from datetime import date
from types import SimpleNamespace

from services.cuentas_pagar_productivas import (
    actualizar_estado, anular_pago, resumen_vencimientos, saldo_obligacion,
    fecha_vencimiento_periodo, ultimo_dia_mes,
)


def obligacion(importe, pagos, vencimiento, estado="pendiente"):
    return SimpleNamespace(
        importe_centavos=importe,
        pagos=[SimpleNamespace(importe_centavos=p, anulado=False) for p in pagos],
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
    assert fecha_vencimiento_periodo(date(2026, 2, 1), 31) == date(2026, 2, 28)


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


def test_bootstrap_recibe_modelos_para_generar_obligaciones_automaticas():
    app = open("app.py", encoding="utf-8").read()
    bootstrap = open("services/bootstrap_base_datos.py", encoding="utf-8").read()
    for nombre in (
        "ReglaAjusteIPCProductivo",
        "ObligacionCostoProductivo",
        "CostoFijoVersion",
    ):
        assert f'"{nombre}":' in app
        assert f'modelos["{nombre}"]' in bootstrap


def test_motor_recurrente_es_idempotente_y_configurable():
    servicio = open("services/cuentas_pagar_productivas.py", encoding="utf-8").read()
    modelo = open("models/cuentas_pagar_productivas.py", encoding="utf-8").read()
    plantilla = open("templates/admin_fuentes_costos.html", encoding="utf-8").read()
    assert "class ReglaObligacionCostoProductivo" in modelo
    assert "def generar_obligaciones_recurrentes" in servicio
    assert "if existente is None:" in servicio
    assert "Automatizar vencimientos recurrentes" in plantilla
    assert "Generación automática activa" in plantilla
    assert "recurring-rules-table" in plantilla
    assert "recurring-rule-dialog" in plantilla
    assert 'id="cuentas-pagar"' in plantilla


def test_job_diario_mantiene_horizonte_de_obligaciones():
    job = open("modules/automation/jobs/ipc_costs.py", encoding="utf-8").read()
    assert "ejecutar_generacion_recurrente" in job
    assert "ReglaObligacionCostoProductivo" in job


def test_pago_anulado_no_reduce_saldo_y_conserva_motivo():
    item = obligacion(10000, [3000], date(2026, 8, 20), estado="parcial")
    pago = item.pagos[0]
    pago.obligacion = item
    sesion = SimpleNamespace(commit=lambda: None)
    anular_pago(
        pago, motivo="Carga duplicada", usuario_id=7, db_session=sesion,
        ahora_fn=lambda: "instante",
    )
    assert saldo_obligacion(item) == 10000
    assert item.estado == "pendiente"
    assert pago.anulado is True
    assert pago.motivo_anulacion == "Carga duplicada"


def test_interfaz_gestiona_comprobante_historial_y_anulacion():
    plantilla = open("templates/admin_fuentes_costos.html", encoding="utf-8").read()
    modelo = open("models/cuentas_pagar_productivas.py", encoding="utf-8").read()
    assert "Comprobante o enlace" in plantilla
    assert "Historial de movimientos" in plantilla
    assert 'value="anular_pago_costo"' in plantilla
    assert "comprobante = db.Column" in modelo
    assert "motivo_anulacion = db.Column" in modelo


def test_migracion_agrega_auditoria_sin_borrar_pagos():
    migraciones = open("services/migraciones_saas.py", encoding="utf-8").read()
    bootstrap = open("services/bootstrap_base_datos.py", encoding="utf-8").read()
    assert "def asegurar_auditoria_pagos_productivos" in migraciones
    assert "asegurar_auditoria_pagos_productivos(" in bootstrap
