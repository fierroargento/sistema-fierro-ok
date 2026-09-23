from modules.automation import manager
from modules.automation.jobs import ipc_costs


def test_manager_no_construye_scheduler_si_llave_central_esta_apagada(monkeypatch):
    construcciones = []
    monkeypatch.setattr(manager, "scheduler_habilitado", lambda: False)
    monkeypatch.setattr(
        manager,
        "BackgroundScheduler",
        lambda **_kwargs: construcciones.append(True),
    )
    monkeypatch.setattr(manager, "_scheduler", None)

    resultado = manager.iniciar_scheduler(lambda: None, lambda: None)

    assert resultado is None
    assert construcciones == []


def test_job_ipc_no_abre_contexto_si_scheduler_esta_apagado(monkeypatch):
    entradas = []

    class App:
        def app_context(self):
            entradas.append("contexto")
            raise AssertionError("No debe abrir contexto")

    monkeypatch.setattr(ipc_costs, "scheduler_habilitado", lambda: False)

    assert ipc_costs.ejecutar_job_ipc_costos(App(), object()) is False
    assert entradas == []


def test_job_ipc_exige_conexion_especifica_antes_de_base(monkeypatch):
    entradas = []

    class App:
        def app_context(self):
            entradas.append("contexto")
            raise AssertionError("No debe abrir contexto")

    monkeypatch.setattr(ipc_costs, "scheduler_habilitado", lambda: True)
    monkeypatch.setattr(
        ipc_costs,
        "conexiones_externas_habilitadas",
        lambda canal: canal != "IPC",
    )

    assert ipc_costs.ejecutar_job_ipc_costos(App(), object()) is False
    assert entradas == []
