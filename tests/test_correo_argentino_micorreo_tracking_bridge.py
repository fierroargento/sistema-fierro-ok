from services import tracking_externo


def test_consultar_correo_formulario_prefiere_micorreo_si_devuelve_estado(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo.micorreo_habilitado",
        lambda: True,
    )

    monkeypatch.setattr(
        "services.correo_argentino_micorreo.consultar_tracking_envio",
        lambda seguimiento: {
            "ok": True,
            "estado": "PREIMPOSICION",
            "eventos": [
                {
                    "evento": "PREIMPOSICION",
                    "fecha": "28-08-2024 10:33",
                    "sucursal": "CORREO ARGENTINO",
                }
            ],
        },
    )

    r = tracking_externo.consultar_correo_formulario("000500076393019A3G0C701")

    assert r["estado"] == "PREIMPOSICION"
    assert r["error"] is None
    assert r["origen"] == "micorreo"
    assert r["raw"]["eventos"][0]["sucursal"] == "CORREO ARGENTINO"
