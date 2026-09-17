from pathlib import Path

import pytest

from services.seguridad_entorno import (
    conexiones_externas_habilitadas,
    diagnostico_laboratorio_desconectado,
    exigir_conexion_externa,
)


CANALES = (
    "ML", "TN", "WHATSAPP", "OPENAI", "CLOUDINARY",
    "ANDREANI", "CORREO", "TRACKING", "GEOCODING",
)


def limpiar(monkeypatch):
    monkeypatch.delenv("SISTEMA_FIERRO_ENTORNO", raising=False)
    monkeypatch.delenv("CONEXIONES_EXTERNAS_HABILITADAS", raising=False)
    for canal in CANALES:
        monkeypatch.delenv(f"{canal}_CONEXION_HABILITADA", raising=False)


def test_laboratorio_arranca_sin_red(monkeypatch):
    limpiar(monkeypatch)
    diagnostico = diagnostico_laboratorio_desconectado()
    assert diagnostico["entorno"] == "desarrollo"
    assert diagnostico["desconectado"] is True
    assert all(
        estado["conexion"] is False
        for estado in diagnostico["canales"].values()
    )


def test_credenciales_o_una_llave_aislada_no_abren_red(monkeypatch):
    limpiar(monkeypatch)
    monkeypatch.setenv("MELI_CLIENT_ID", "credencial-presente")
    monkeypatch.setenv("CONEXIONES_EXTERNAS_HABILITADAS", "true")
    assert conexiones_externas_habilitadas("ML") is False


def test_habilitacion_exige_entorno_maestra_y_canal(monkeypatch):
    limpiar(monkeypatch)
    monkeypatch.setenv("SISTEMA_FIERRO_ENTORNO", "staging")
    monkeypatch.setenv("CONEXIONES_EXTERNAS_HABILITADAS", "true")
    assert conexiones_externas_habilitadas("ML") is False
    monkeypatch.setenv("ML_CONEXION_HABILITADA", "true")
    assert conexiones_externas_habilitadas("ML") is True
    assert conexiones_externas_habilitadas("TN") is False


def test_barrera_falla_antes_de_abrir_socket(monkeypatch):
    limpiar(monkeypatch)
    with pytest.raises(RuntimeError, match="laboratorio desconectado"):
        exigir_conexion_externa("OPENAI", "Consulta OpenAI")


def test_clientes_criticos_exigen_barrera_de_red():
    contratos = {
        "modules/bot_ml/api_client.py": 'exigir_conexion_externa("ML"',
        "modules/whatsapp/media_inbound.py": 'exigir_conexion_externa("WHATSAPP"',
        "services/ia.py": 'exigir_conexion_externa("OPENAI"',
        "services/andreani.py": 'exigir_conexion_externa("ANDREANI"',
        "services/correo_argentino_micorreo.py": 'exigir_conexion_externa("CORREO"',
        "services/tracking_externo.py": 'exigir_conexion_externa("TRACKING"',
    }
    for ruta, contrato in contratos.items():
        fuente = Path(ruta).read_text(encoding="utf-8-sig")
        assert contrato in fuente, ruta


def test_tienda_nube_y_cargas_exigen_barrera():
    app = Path("app.py").read_text(encoding="utf-8-sig")
    pagos = Path("services/comprobantes_pagos_productivos.py").read_text(encoding="utf-8-sig")
    catalogo = Path("services/catalogo_ficha_integral.py").read_text(encoding="utf-8-sig")
    assert 'exigir_conexion_externa("TN"' in app
    assert 'exigir_conexion_externa("CLOUDINARY"' in pagos
    assert 'exigir_conexion_externa("CLOUDINARY"' in catalogo
