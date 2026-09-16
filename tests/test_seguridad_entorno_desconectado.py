from pathlib import Path

import pytest

from services.seguridad_entorno import (
    bootstrap_base_habilitado, efectos_externos_habilitados, entorno_actual,
    exigir_efecto_externo, procesamiento_webhook_habilitado, scheduler_habilitado,
)


VARIABLES = [
    "SISTEMA_FIERRO_ENTORNO", "EFECTOS_EXTERNOS_HABILITADOS",
    "WHATSAPP_EFECTOS_HABILITADOS", "ML_EFECTOS_HABILITADOS",
    "WEBHOOKS_HABILITADOS", "ML_WEBHOOK_HABILITADO",
    "SCHEDULER_ENABLED", "BOOTSTRAP_BASE_DATOS_HABILITADO",
]


def limpiar(monkeypatch):
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)


def test_defaults_son_desconectados(monkeypatch):
    limpiar(monkeypatch)
    assert entorno_actual() == "desarrollo"
    assert efectos_externos_habilitados("WHATSAPP") is False
    assert procesamiento_webhook_habilitado("ML") is False
    assert scheduler_habilitado() is False
    assert bootstrap_base_habilitado() is False


def test_un_flag_aislado_no_alcanza(monkeypatch):
    limpiar(monkeypatch)
    monkeypatch.setenv("EFECTOS_EXTERNOS_HABILITADOS", "true")
    monkeypatch.setenv("WHATSAPP_EFECTOS_HABILITADOS", "true")
    assert efectos_externos_habilitados("WHATSAPP") is False


def test_doble_habilitacion_y_entorno_son_obligatorios(monkeypatch):
    limpiar(monkeypatch)
    monkeypatch.setenv("SISTEMA_FIERRO_ENTORNO", "staging")
    monkeypatch.setenv("EFECTOS_EXTERNOS_HABILITADOS", "true")
    assert efectos_externos_habilitados("ML") is False
    monkeypatch.setenv("ML_EFECTOS_HABILITADOS", "true")
    assert efectos_externos_habilitados("ML") is True


def test_exigir_efecto_falla_cerrado(monkeypatch):
    limpiar(monkeypatch)
    with pytest.raises(RuntimeError, match="modo desconectado"):
        exigir_efecto_externo("TN", "Prueba")


def test_contratos_criticos_estan_conectados_a_la_barrera():
    app = Path("app.py").read_text(encoding="utf-8-sig")
    sender = Path("modules/whatsapp/sender.py").read_text(encoding="utf-8-sig")
    bootstrap = Path("services/bootstrap_base_datos.py").read_text(encoding="utf-8-sig")
    assert 'exigir_efecto_externo("ML"' in app
    assert 'exigir_efecto_externo("TN"' in app
    assert 'procesamiento_webhook_habilitado("ML")' in app
    assert 'procesamiento_webhook_habilitado("TN")' in app
    assert 'efectos_externos_habilitados("WHATSAPP")' in sender
    assert "bootstrap_base_habilitado()" in bootstrap


def test_fronteras_tenant_criticas_no_son_globales():
    app = Path("app.py").read_text(encoding="utf-8-sig")
    assert "Producto.organizacion_id == membresia.organizacion_id" in app
    assert "Pedido.organizacion_id == membresia.organizacion_id" in app
    assert "organizacion_id=membresia_pedido.organizacion_id" in app
