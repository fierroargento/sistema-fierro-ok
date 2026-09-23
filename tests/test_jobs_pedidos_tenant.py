from pathlib import Path
from types import SimpleNamespace

import pytest

from services.acceso_tenant_pedidos import consulta_pedidos_job_tenant


class Query:
    def __init__(self, datos):
        self.datos = list(datos)

    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave) == valor for clave, valor in filtros.items())
        ])

    def all(self):
        return self.datos


class PedidoModelo:
    query = Query([])


def test_consulta_job_exige_y_filtra_un_tenant_concreto():
    PedidoModelo.query = Query([
        SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=100),
        SimpleNamespace(id=2, organizacion_id=10, unidad_negocio_id=101),
        SimpleNamespace(id=3, organizacion_id=20, unidad_negocio_id=100),
        SimpleNamespace(id=4, organizacion_id=None, unidad_negocio_id=None),
    ])
    assert [
        p.id for p in consulta_pedidos_job_tenant(PedidoModelo, 10, 100).all()
    ] == [1]
    with pytest.raises(ValueError, match="organización"):
        consulta_pedidos_job_tenant(PedidoModelo, None, 100)
    with pytest.raises(ValueError, match="unidad"):
        consulta_pedidos_job_tenant(PedidoModelo, 10, None)


def test_job_ml_particiona_sus_dos_conjuntos_por_tenant():
    texto = Path("modules/automation/jobs/ml_messages.py").read_text(encoding="utf-8")
    assert "unidad_negocio_id," in texto
    assert texto.count("Pedido, organizacion_id, unidad_negocio_id,") == 2
    assert "Pedido.query" not in texto


def test_scheduler_wa_particiona_recordatorios_y_tracking():
    texto = Path("modules/whatsapp/scheduler.py").read_text(encoding="utf-8")
    assert "def ejecutar_timers(*, organizacion_id, unidad_negocio_id):" in texto
    assert texto.count("Pedido, organizacion_id, unidad_negocio_id,") == 2
    assert "Pedido.query" not in texto


def test_wrapper_wa_propaga_tenant_obligatorio():
    texto = Path("modules/automation/jobs/wa_timers.py").read_text(encoding="utf-8")
    assert "unidad_negocio_id," in texto
    assert "unidad_negocio_id=unidad_negocio_id" in texto


def test_orquestador_recorrer_organizaciones_activas_por_separado():
    texto = Path("app.py").read_text(encoding="utf-8")
    bloque = texto.split("def _job_ml_mensajes():", 1)[1].split(
        "def _job_ipc_costos():", 1
    )[0]
    assert bloque.count("Organizacion.query.filter_by(activa=True).all()") == 2
    assert bloque.count("organizacion_id=organizacion.id") == 4
    assert bloque.count("UnidadNegocio.query.filter_by(") == 2
    assert bloque.count("unidad_negocio_id=unidad.id") == 2


def test_job_ml_falla_cerrado_antes_de_contexto_o_base(monkeypatch):
    from modules.automation.jobs import ml_messages

    entradas = []

    class App:
        def app_context(self):
            entradas.append("contexto")
            raise AssertionError("No debe abrir contexto")

    monkeypatch.setattr(ml_messages, "scheduler_habilitado", lambda: True)
    monkeypatch.setattr(
        ml_messages,
        "conexiones_externas_habilitadas",
        lambda _canal: False,
    )
    monkeypatch.setattr(
        ml_messages,
        "efectos_externos_habilitados",
        lambda _canal: True,
    )

    assert ml_messages.ejecutar_job_ml_mensajes(
        App(), object(), organizacion_id=10, unidad_negocio_id=100,
    ) is False
    assert entradas == []


def test_migracion_no_activa_scheduler_ni_agrega_transporte():
    archivos = (
        "services/acceso_tenant_pedidos.py",
        "modules/automation/jobs/wa_timers.py",
    )
    texto = "\n".join(Path(p).read_text(encoding="utf-8") for p in archivos).lower()
    for prohibido in ("scheduler_enabled = true", "requests", "oauth", "access_token"):
        assert prohibido not in texto
