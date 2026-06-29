from services.transporte_revision import (
    TIPO_ERROR_DATOS,
    TIPO_ERROR_INTEGRACION,
    TIPO_ERROR_REVISION,
    TIPO_ERROR_SIN_COBERTURA,
    clasificar_motivo_transporte,
    construir_marca_revision_transporte,
)


def test_no_marca_sin_cobertura_si_fallo_cotizacion_correo():
    motivo = "No se pudo cotizar Correo para CP 9000. Revisar respuesta de la integracion."

    marca = construir_marca_revision_transporte("9000", motivo)

    assert marca.startswith("Transporte requiere revision tecnica CP 9000")
    assert "Sin cobertura" not in marca
    assert motivo in marca


def test_marca_sin_cobertura_solo_si_motivo_lo_indica():
    marca = construir_marca_revision_transporte(
        "6070",
        "Sin cobertura Correo para el CP informado",
    )

    assert marca.startswith("Sin cobertura transportes CP 6070")


def test_clasifica_error_autenticacion_como_integracion():
    assert clasificar_motivo_transporte(
        "No se pudo autenticar con Correo Argentino. Revisar credenciales."
    ) == TIPO_ERROR_INTEGRACION


def test_clasifica_datos_logisticos_incompletos():
    assert clasificar_motivo_transporte(
        "Datos logisticos incompletos para cotizar Correo."
    ) == TIPO_ERROR_DATOS


def test_clasifica_motivo_desconocido_como_revision():
    assert clasificar_motivo_transporte("Revisar operador transporte") == TIPO_ERROR_REVISION


def test_clasifica_sin_cobertura_real():
    assert clasificar_motivo_transporte("Sin cobertura transportes CP 9000") == TIPO_ERROR_SIN_COBERTURA
