import json

import pytest

from modules.automation.jobs.ipc_costs import (
    ejecutar_tareas_ipc_resilientes,
)


class SesionFake:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


def modelos_fake():
    return {
        "IndiceIPCOficial": object(),
        "ReglaAjusteIPCProductivo": object(),
        "PropuestaAjusteIPCProductivo": object(),
        "CostoFijoVersion": object(),
        "ObligacionCostoProductivo": object(),
        "ReglaObligacionCostoProductivo": object(),
    }


def generador_fake(registro):
    def generar(**kwargs):
        registro.append(kwargs)
        return 4

    return generar


def test_timeout_reintenta_y_luego_continua_obligaciones():
    sesion = SesionFake()
    llamadas = []
    generaciones = []
    esperas = []

    def ciclo(**kwargs):
        llamadas.append(kwargs)
        if len(llamadas) == 1:
            raise TimeoutError("The read operation timed out")

    resultado = ejecutar_tareas_ipc_resilientes(
        ejecutar_ciclo_fn=ciclo,
        generar_recurrente_fn=generador_fake(generaciones),
        modelos=modelos_fake(),
        db_session=sesion,
        sleep_fn=esperas.append,
        logger_fn=lambda mensaje: None,
    )

    assert len(llamadas) == 2
    assert sesion.rollbacks == 1
    assert esperas == [3]
    assert len(generaciones) == 1
    assert resultado == {
        "ipc_actualizado": True,
        "obligaciones_generadas": 4,
    }


def test_api_caida_no_impide_obligaciones_recurrentes():
    sesion = SesionFake()
    generaciones = []
    logs = []

    def ciclo(**kwargs):
        raise TimeoutError("API IPC no disponible")

    resultado = ejecutar_tareas_ipc_resilientes(
        ejecutar_ciclo_fn=ciclo,
        generar_recurrente_fn=generador_fake(generaciones),
        modelos=modelos_fake(),
        db_session=sesion,
        sleep_fn=lambda segundos: None,
        logger_fn=logs.append,
    )

    assert sesion.rollbacks == 2
    assert len(logs) == 2
    assert len(generaciones) == 1
    assert resultado == {
        "ipc_actualizado": False,
        "obligaciones_generadas": 4,
    }


def test_json_invalido_es_transitorio_y_hace_rollback():
    sesion = SesionFake()
    generaciones = []

    def ciclo(**kwargs):
        raise json.JSONDecodeError("JSON inválido", "{", 0)

    resultado = ejecutar_tareas_ipc_resilientes(
        ejecutar_ciclo_fn=ciclo,
        generar_recurrente_fn=generador_fake(generaciones),
        modelos=modelos_fake(),
        db_session=sesion,
        intentos=1,
        logger_fn=lambda mensaje: None,
    )

    assert sesion.rollbacks == 1
    assert len(generaciones) == 1
    assert resultado["ipc_actualizado"] is False


def test_error_funcional_no_se_oculta_ni_ejecuta_tareas_posteriores():
    sesion = SesionFake()
    generaciones = []

    def ciclo(**kwargs):
        raise ValueError("Regla IPC inválida")

    with pytest.raises(ValueError, match="Regla IPC inválida"):
        ejecutar_tareas_ipc_resilientes(
            ejecutar_ciclo_fn=ciclo,
            generar_recurrente_fn=generador_fake(generaciones),
            modelos=modelos_fake(),
            db_session=sesion,
            sleep_fn=lambda segundos: None,
            logger_fn=lambda mensaje: None,
        )

    assert sesion.rollbacks == 0
    assert generaciones == []
