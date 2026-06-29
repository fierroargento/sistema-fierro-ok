from services.correo_argentino_operacion import evaluar_oferta_sucursales_correo_pp6040


def prefs(umbral=10000):
    return {"max_costo_correo_sucursal_pp6040": umbral}


def test_no_ofrece_sucursales_si_costo_no_validado_y_conserva_motivo_real():
    resultado = evaluar_oferta_sucursales_correo_pp6040(
        {},
        preferencias=prefs(),
        resultado_cotizacion={
            "error": "No se pudo cotizar Correo para CP 9000. Revisar respuesta de la integracion.",
            "tipo_error": "error_integracion",
        },
    )

    assert resultado["ofrecer_sucursales"] is False
    assert resultado["requiere_operador"] is True
    assert resultado["costo_validado"] is False
    assert resultado["tipo_error"] == "error_integracion"
    assert resultado["motivo"].startswith("Costo Correo sucursal PP6040 no validado")
    assert "No se pudo cotizar Correo para CP 9000" in resultado["motivo"]


def test_ofrece_sucursales_si_costo_validado_bajo_umbral():
    resultado = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": 9000},
        preferencias=prefs(umbral=10000),
    )

    assert resultado["ofrecer_sucursales"] is True
    assert resultado["costo_validado"] is True


def test_no_ofrece_sucursales_si_costo_validado_supera_umbral():
    resultado = evaluar_oferta_sucursales_correo_pp6040(
        {"disponible": True, "precio": 12000},
        preferencias=prefs(umbral=10000),
    )

    assert resultado["ofrecer_sucursales"] is False
    assert resultado["requiere_operador"] is True
    assert resultado["costo_validado"] is True
    assert "supera el umbral" in resultado["motivo"]
