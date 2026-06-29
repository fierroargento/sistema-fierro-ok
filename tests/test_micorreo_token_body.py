from types import SimpleNamespace

from services import correo_argentino_micorreo as micorreo


class FakeResponse:
    status = 200

    def read(self):
        return b'{"token":"TOKEN_PRUEBA","expire":"2026-06-29 15:13:40"}'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_obtener_token_envia_body_json_vacio(monkeypatch):
    capturado = {}

    def fake_urlopen(req, timeout):
        capturado["data"] = req.data
        capturado["headers"] = dict(req.header_items())
        capturado["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(micorreo, "urlopen", fake_urlopen)

    cfg = SimpleNamespace(
        enabled=True,
        base_url="https://api.correoargentino.com.ar/micorreo/v1",
        integracion_user="usuario",
        integracion_pass="clave",
        timeout=20,
    )

    resultado = micorreo.obtener_token(config=cfg)

    assert resultado["ok"] is True
    assert resultado["token"] == "TOKEN_PRUEBA"
    assert capturado["data"] == b"{}"

    headers = {k.lower(): v for k, v in capturado["headers"].items()}
    assert headers["content-type"] == "application/json"
    assert headers["authorization"].startswith("Basic ")
    assert capturado["timeout"] == 20
