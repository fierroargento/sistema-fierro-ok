from modules.transportes import correo_argentino


class PedidoFake:
    provincia = "Río Negro"
    codigo_postal = "8400"
    localidad = "Bariloche"
    direccion = "Mitre 100"


def test_cotizar_correo_delega_a_micorreo_si_esta_habilitado(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo.micorreo_habilitado",
        lambda: True,
    )

    def fake_cotizar_envio(**kwargs):
        assert kwargs["cp_destino"] == "1000"
        assert kwargs["modalidad"] == "D"
        return {
            "ok": True,
            "status": 202,
            "cotizaciones": [
                {
                    "producto": "Correo Argentino Clasico",
                    "precio": 15957.0,
                    "plazo_min": 2,
                    "plazo_max": 5,
                    "modalidad": "D",
                }
            ],
        }

    monkeypatch.setattr(
        "services.correo_argentino_micorreo.cotizar_envio",
        fake_cotizar_envio,
    )

    r = correo_argentino.cotizar_correo("1000", tipo_entrega="D")

    assert r["disponible"] is True
    assert r["precio"] == 15957.0
    assert r["plazo_dias"] == 5
    assert r["servicio"] == "Correo Argentino Clasico"
    assert r["tipo"] == "correo_argentino_micorreo"


def test_cotizar_correo_micorreo_sin_tarifas_devuelve_no_disponible(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo.micorreo_habilitado",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.correo_argentino_micorreo.cotizar_envio",
        lambda **kwargs: {"ok": True, "status": 202, "cotizaciones": []},
    )

    r = correo_argentino.cotizar_correo("1000", tipo_entrega="S")

    assert r["disponible"] is False
    assert r["precio"] is None
    assert "tarifas" in r["error"].lower()


def test_obtener_sucursales_correo_por_pedido_delega_a_micorreo(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo.micorreo_habilitado",
        lambda: True,
    )

    def fake_consultar_sucursales(province_code=None):
        assert province_code == "R"
        return {
            "ok": True,
            "sucursales": [
                {
                    "id": "R0100",
                    "codigo": "R0100",
                    "nombre": "S. C. DE BARILOCHE",
                    "direccion": "Mitre 100",
                    "localidad": "Bariloche",
                    "provincia": "Río Negro",
                    "cp": "8400",
                }
            ],
        }

    monkeypatch.setattr(
        "services.correo_argentino_micorreo.consultar_sucursales",
        fake_consultar_sucursales,
    )

    r = correo_argentino.obtener_sucursales_correo_por_pedido(PedidoFake())

    assert len(r) == 1
    assert r[0]["codigo"] == "R0100"
    assert r[0]["nombre"] == "S. C. DE BARILOCHE"
