from datetime import datetime, timedelta

import pytest

from modules.bot_ml import api_client


class CuentaFake:
    def __init__(self):
        self.access_token = ""
        self.refresh_token = ""
        self.token_expires_at = None
        self.scope = ""
        self.estado_conexion = ""


def test_ml_config_faltante_detecta_variables_vacias(monkeypatch):
    monkeypatch.delenv("MELI_CLIENT_ID", raising=False)
    monkeypatch.delenv("MELI_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("MELI_REDIRECT_URI", raising=False)

    assert api_client.ml_config_faltante() == [
        "MELI_CLIENT_ID",
        "MELI_CLIENT_SECRET",
        "MELI_REDIRECT_URI",
    ]


def test_ml_config_faltante_sin_faltantes(monkeypatch):
    monkeypatch.setenv("MELI_CLIENT_ID", "client-id")
    monkeypatch.setenv("MELI_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MELI_REDIRECT_URI", "https://sistema.test/callback")

    assert api_client.ml_config_faltante() == []


def test_ml_token_vencido_si_no_hay_cuenta():
    assert api_client.ml_token_vencido(None) is True


def test_ml_token_vencido_si_no_hay_expiracion():
    cuenta = CuentaFake()

    assert api_client.ml_token_vencido(cuenta) is True


def test_ml_token_vencido_si_expira_en_menos_de_dos_minutos():
    cuenta = CuentaFake()
    cuenta.token_expires_at = datetime.utcnow() + timedelta(seconds=30)

    assert api_client.ml_token_vencido(cuenta) is True


def test_ml_token_no_vencido_si_expira_mas_adelante():
    cuenta = CuentaFake()
    cuenta.token_expires_at = datetime.utcnow() + timedelta(minutes=10)

    assert api_client.ml_token_vencido(cuenta) is False


def test_ml_guardar_token_en_cuenta_actualiza_campos():
    cuenta = CuentaFake()
    cuenta.access_token = "anterior"
    cuenta.refresh_token = "refresh-anterior"

    api_client.ml_guardar_token_en_cuenta(
        cuenta,
        {
            "access_token": "nuevo-token",
            "refresh_token": "nuevo-refresh",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    assert cuenta.access_token == "nuevo-token"
    assert cuenta.refresh_token == "nuevo-refresh"
    assert cuenta.scope == "read write"
    assert cuenta.estado_conexion == "conectada"
    assert cuenta.token_expires_at is not None


def test_ml_guardar_token_en_cuenta_conserva_refresh_si_no_viene():
    cuenta = CuentaFake()
    cuenta.access_token = "anterior"
    cuenta.refresh_token = "refresh-anterior"

    api_client.ml_guardar_token_en_cuenta(
        cuenta,
        {
            "access_token": "nuevo-token",
            "expires_in": 0,
        },
    )

    assert cuenta.access_token == "nuevo-token"
    assert cuenta.refresh_token == "refresh-anterior"
    assert cuenta.estado_conexion == "conectada"


def test_ml_refresh_access_token_requiere_refresh_token():
    cuenta = CuentaFake()

    with pytest.raises(ValueError) as exc:
        api_client.ml_refresh_access_token(cuenta)

    assert "refresh token" in str(exc.value)


def test_ml_refresh_access_token_actualiza_cuenta(monkeypatch):
    cuenta = CuentaFake()
    cuenta.refresh_token = "refresh-token"

    monkeypatch.setenv("MELI_CLIENT_ID", "client-id")
    monkeypatch.setenv("MELI_CLIENT_SECRET", "secret")

    def fake_http_json(method, url, data=None, headers=None):
        assert method == "POST"
        assert url == "https://api.mercadolibre.com/oauth/token"
        assert data["grant_type"] == "refresh_token"
        assert data["client_id"] == "client-id"
        assert data["client_secret"] == "secret"
        assert data["refresh_token"] == "refresh-token"

        return {
            "access_token": "access-nuevo",
            "refresh_token": "refresh-nuevo",
            "expires_in": 3600,
            "scope": "offline_access",
        }

    monkeypatch.setattr(api_client, "ml_http_json", fake_http_json)

    resultado = api_client.ml_refresh_access_token(cuenta)

    assert resultado is cuenta
    assert cuenta.access_token == "access-nuevo"
    assert cuenta.refresh_token == "refresh-nuevo"
    assert cuenta.scope == "offline_access"
    assert cuenta.estado_conexion == "conectada"