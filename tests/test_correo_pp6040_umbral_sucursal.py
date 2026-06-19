from services.correo_argentino_operacion import (
    evaluar_oferta_sucursales_correo_pp6040,
    obtener_preferencias_operativas_correo,
)


def test_preferencias_correo_incluyen_umbral_pp6040(monkeypatch):
    monkeypatch.setenv("CORREO_MAX_COSTO_SUCURSAL_PP6040", "10000")

    prefs = obtener_preferencias_operativas_correo()

    assert prefs["max_costo_correo_sucursal_pp6040"] == 10000


def test_pp6040_ofrece_sucursales_si_costo_no_supera_umbral():
    decision = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": 9999},
        preferencias={"max_costo_correo_sucursal_pp6040": 10000},
    )

    assert decision["ofrecer_sucursales"] is True
    assert decision["requiere_operador"] is False
    assert decision["precio"] == 9999
    assert decision["umbral"] == 10000


def test_pp6040_no_ofrece_sucursales_si_costo_supera_umbral():
    decision = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": 12000},
        preferencias={"max_costo_correo_sucursal_pp6040": 10000},
    )

    assert decision["ofrecer_sucursales"] is False
    assert decision["requiere_operador"] is True
    assert "supera el umbral" in decision["motivo"]


def test_pp6040_no_ofrece_sucursales_si_no_hay_precio():
    decision = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": None},
        preferencias={"max_costo_correo_sucursal_pp6040": 10000},
    )

    assert decision["ofrecer_sucursales"] is False
    assert decision["requiere_operador"] is True


def test_pp6040_no_ofrece_sucursales_si_umbral_apagado():
    decision = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": 5000},
        preferencias={"max_costo_correo_sucursal_pp6040": 0},
    )

    assert decision["ofrecer_sucursales"] is False
    assert decision["requiere_operador"] is True
