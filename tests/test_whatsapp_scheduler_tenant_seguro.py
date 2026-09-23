from pathlib import Path

import pytest

from modules.whatsapp import scheduler


def test_tick_desconectado_corta_antes_de_jobs_y_base(monkeypatch):
    llamados = []
    monkeypatch.setattr(scheduler, "scheduler_habilitado", lambda: False)
    monkeypatch.setattr(
        scheduler, "ejecutar_timers_whatsapp",
        lambda **_kwargs: llamados.append("whatsapp"),
    )
    monkeypatch.setattr(
        scheduler, "ejecutar_tracking_automatico",
        lambda **_kwargs: llamados.append("tracking"),
    )

    assert scheduler.ejecutar_timers(
        organizacion_id=7, unidad_negocio_id=70,
    ) is False
    assert llamados == []


def test_tick_habilitado_propaga_un_mismo_tenant(monkeypatch):
    llamados = []
    monkeypatch.setattr(scheduler, "scheduler_habilitado", lambda: True)
    monkeypatch.setattr(
        scheduler, "ejecutar_timers_whatsapp",
        lambda **kwargs: llamados.append((
            "whatsapp", kwargs["organizacion_id"], kwargs["unidad_negocio_id"],
        )),
    )
    monkeypatch.setattr(
        scheduler, "ejecutar_tracking_automatico",
        lambda **kwargs: llamados.append((
            "tracking", kwargs["organizacion_id"], kwargs["unidad_negocio_id"],
        )),
    )
    monkeypatch.setattr(
        scheduler, "_cerrar_sesion_db_segura",
        lambda **_kwargs: None,
    )

    assert scheduler.ejecutar_timers(
        organizacion_id="7", unidad_negocio_id="70",
    ) is True
    assert llamados == [("whatsapp", 7, 70), ("tracking", 7, 70)]


@pytest.mark.parametrize("organizacion_id", [None, "", 0, -1, "abc"])
def test_scheduler_rechaza_tenant_invalido(organizacion_id):
    with pytest.raises(ValueError, match="organización"):
        scheduler.ejecutar_timers(
            organizacion_id=organizacion_id, unidad_negocio_id=70,
        )


@pytest.mark.parametrize("unidad_negocio_id", [None, "", 0, -1, "abc"])
def test_scheduler_rechaza_unidad_invalida(unidad_negocio_id):
    with pytest.raises(ValueError, match="unidad"):
        scheduler.ejecutar_timers(
            organizacion_id=7, unidad_negocio_id=unidad_negocio_id,
        )


def test_recordatorios_exigen_scheduler_conexion_y_efectos(monkeypatch):
    consultas = []
    monkeypatch.setattr(
        scheduler, "consulta_pedidos_job_tenant",
        lambda *_args, **_kwargs: consultas.append("consulta"),
    )
    monkeypatch.setattr(scheduler, "scheduler_habilitado", lambda: True)
    monkeypatch.setattr(
        scheduler, "conexiones_externas_habilitadas", lambda _canal: True,
    )
    monkeypatch.setattr(
        scheduler, "efectos_externos_habilitados", lambda _canal: False,
    )

    assert scheduler.ejecutar_timers_whatsapp(
        organizacion_id=1, unidad_negocio_id=10,
    ) is False
    assert consultas == []


def test_tracking_exige_scheduler_y_conexion_especifica(monkeypatch):
    consultas = []
    monkeypatch.setattr(
        scheduler, "consulta_pedidos_job_tenant",
        lambda *_args, **_kwargs: consultas.append("consulta"),
    )
    monkeypatch.setattr(scheduler, "scheduler_habilitado", lambda: True)
    monkeypatch.setattr(
        scheduler, "conexiones_externas_habilitadas", lambda canal: canal != "TRACKING",
    )

    assert scheduler.ejecutar_tracking_automatico(
        organizacion_id=1, unidad_negocio_id=10,
    ) is False
    assert consultas == []


def test_scheduler_ya_no_depende_de_credenciales_globales():
    fuente = Path("modules/whatsapp/scheduler.py").read_text(encoding="utf-8-sig")
    assert "modulo_activo" not in fuente
    assert 'efectos_externos_habilitados("WHATSAPP")' in fuente
    assert 'conexiones_externas_habilitadas("WHATSAPP")' in fuente
    assert 'conexiones_externas_habilitadas("TRACKING")' in fuente
