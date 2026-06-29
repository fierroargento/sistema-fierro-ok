from modules.transportes import correo_argentino
from services import correo_argentino_micorreo


def test_cotizacion_legacy_desde_micorreo_toma_primera_cotizacion():
    resultado = correo_argentino._cotizacion_legacy_desde_micorreo(
        {
            "ok": True,
            "status": 202,
            "tipo": "correo_argentino_micorreo",
            "cotizaciones": [
                {
                    "producto": "Correo Argentino Clasico",
                    "precio": 10636.0,
                    "plazo_min": "2",
                    "plazo_max": "5",
                    "modalidad": "S",
                }
            ],
        },
        tipo_entrega="S",
    )

    assert resultado["disponible"] is True
    assert resultado["precio"] == 10636.0
    assert resultado["plazo_dias"] == "5"
    assert resultado["servicio"] == "Correo Argentino Clasico"
    assert resultado["modalidad"] == "S"
    assert resultado["tipo"] == "correo_argentino_micorreo"


def test_cotizacion_legacy_desde_micorreo_con_error_conserva_motivo():
    resultado = correo_argentino._cotizacion_legacy_desde_micorreo(
        {
            "ok": False,
            "status": 504,
            "tipo": "correo_argentino_micorreo",
            "error": "No se pudo obtener token MiCorreo.",
            "respuesta": {"raw": "504"},
        },
        tipo_entrega="S",
    )

    assert resultado["disponible"] is False
    assert resultado["precio"] is None
    assert resultado["status"] == 504
    assert resultado["error"] == "No se pudo obtener token MiCorreo."
    assert resultado["respuesta"] == {"raw": "504"}


def test_cotizar_correo_usa_micorreo_y_devuelve_formato_legacy(monkeypatch):
    monkeypatch.setattr(correo_argentino_micorreo, "micorreo_habilitado", lambda: True)
    monkeypatch.setattr(
        correo_argentino_micorreo,
        "cotizar_envio",
        lambda **kwargs: {
            "ok": True,
            "status": 202,
            "tipo": "correo_argentino_micorreo",
            "cotizaciones": [
                {
                    "producto": "Correo Argentino Clasico",
                    "precio": 10636.0,
                    "plazo_min": "2",
                    "plazo_max": "5",
                    "modalidad": "S",
                }
            ],
        },
    )

    resultado = correo_argentino.cotizar_correo(
        "9000",
        tipo_entrega="S",
        peso_gr=3000,
        alto_cm=6,
        ancho_cm=30,
        largo_cm=40,
    )

    assert resultado["disponible"] is True
    assert resultado["precio"] == 10636.0
    assert resultado["plazo_dias"] == "5"
    assert resultado["tipo"] == "correo_argentino_micorreo"
