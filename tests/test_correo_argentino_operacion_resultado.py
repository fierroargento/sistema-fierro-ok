from services.correo_argentino_operacion import (
    ResultadoPreparacionTransporteCorreo,
)


def test_resultado_transporte_correo_asignada():
    resultado = ResultadoPreparacionTransporteCorreo.asignada(
        "Correo Argentino asignado (Sucursal)",
    )

    assert resultado.ok is True
    assert resultado.escalada is False
    assert resultado.error is False
    assert resultado.estado == "asignada"
    assert resultado.requiere_persistencia is True
    assert resultado.requiere_rollback is False


def test_resultado_transporte_correo_sin_asignacion():
    resultado = (
        ResultadoPreparacionTransporteCorreo.sin_asignacion(
            "Cotización Correo temporalmente deshabilitada",
        )
    )

    assert resultado.ok is False
    assert resultado.escalada is False
    assert resultado.error is False
    assert resultado.estado == "sin_asignacion"
    assert resultado.requiere_persistencia is False
    assert resultado.requiere_rollback is False


def test_resultado_transporte_correo_escalada():
    resultado = (
        ResultadoPreparacionTransporteCorreo.escalada_por(
            "Revisión manual transporte Correo",
        )
    )

    assert resultado.ok is False
    assert resultado.escalada is True
    assert resultado.error is False
    assert resultado.estado == "escalada"
    assert resultado.requiere_persistencia is False
    assert resultado.requiere_rollback is False


def test_resultado_transporte_correo_fallida():
    resultado = ResultadoPreparacionTransporteCorreo.fallida(
        "Error asignando Correo",
    )

    assert resultado.ok is False
    assert resultado.escalada is False
    assert resultado.error is True
    assert resultado.estado == "error"
    assert resultado.requiere_persistencia is False
    assert resultado.requiere_rollback is True
