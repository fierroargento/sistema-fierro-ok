from datetime import date

from services.ajustes_costos_ipc import calcular_ajuste, ventana_para_ajuste


def test_ventana_septiembre_toma_marzo_agosto_con_base_febrero():
    ventana = ventana_para_ajuste(
        date(2026, 9, 1), periodo_inicio=date(2026, 3, 1),
        periodo_final=date(2026, 8, 1), frecuencia_meses=6,
    )
    assert ventana == {
        "inicio": date(2026, 3, 1),
        "final": date(2026, 8, 1),
        "base": date(2026, 2, 1),
    }


def test_ventana_marzo_toma_septiembre_febrero():
    ventana = ventana_para_ajuste(
        date(2027, 3, 1), periodo_inicio=date(2026, 9, 1),
        periodo_final=date(2027, 2, 1), frecuencia_meses=6,
    )
    assert ventana["inicio"] == date(2026, 9, 1)
    assert ventana["final"] == date(2027, 2, 1)
    assert ventana["base"] == date(2026, 8, 1)


def test_ajuste_usa_cociente_de_indices_y_redondea_centavos():
    importe, variacion = calcular_ajuste(121800000, "100", "112.5")
    assert importe == 137025000
    assert variacion == 12.5


def test_confirmacion_manual_y_job_quedan_modulares():
    from pathlib import Path
    servicio = Path("services/ajustes_costos_ipc.py").read_text(encoding="utf-8")
    manager = Path("modules/automation/manager.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert "def aprobar_propuesta" in servicio
    assert 'estado="pendiente"' in servicio
    assert "job_ipc_costos" in manager
    assert "Ningún importe cambia sin aprobación" in plantilla


def test_interfaz_permite_configurar_frecuencia_periodo_y_pago():
    from pathlib import Path
    plantilla = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    modelo = Path("models/ajuste_ipc_productivo.py").read_text(encoding="utf-8")
    assert "Configurar ajuste" in plantilla
    assert 'name="frecuencia_meses"' in plantilla
    assert 'name="periodo_ipc_inicio"' in plantilla
    assert 'name="periodo_ipc_final"' in plantilla
    assert 'name="modalidad_pago"' in plantilla
    assert "ReglaAjusteCostoHistorial" in modelo
