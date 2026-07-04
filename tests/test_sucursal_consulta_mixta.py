from types import SimpleNamespace

from services.sucursal_consulta_mixta import (
    MARCA_HORARIOS_RETIRO,
    agregar_respuesta_neutra_horarios_retiro,
    cliente_consulta_horarios_retiro,
    marcar_consulta_horarios_retiro_pendiente,
)


def test_detecta_consulta_horarios_en_mensaje_mixto():
    texto = "Quilmes Oeste SE LOGISTICA, Av Calchaqui 1564, Quilmes Oeste. Horarios para retirar?"
    assert cliente_consulta_horarios_retiro(texto) is True


def test_no_detecta_horarios_si_solo_confirma_sucursal():
    texto = "Quilmes Oeste SE LOGISTICA, Av Calchaqui 1564, Quilmes Oeste"
    assert cliente_consulta_horarios_retiro(texto) is False


def test_agrega_respuesta_neutra_horarios():
    base = "Perfecto, confirmamos la sucursal elegida."
    texto = "Horarios para retirar?"

    resultado = agregar_respuesta_neutra_horarios_retiro(base, texto)

    assert "confirmamos la sucursal" in resultado
    assert "Sobre los horarios" in resultado
    assert "operador" in resultado


def test_marca_pendiente_operador_por_horarios_no_bloquea_sucursal():
    pedido = SimpleNamespace(
        ia_resumen="",
        ml_mensajes_pendientes=False,
        ml_mensajes_pendientes_count=0,
        ia_requiere_operador=False,
    )

    ok = marcar_consulta_horarios_retiro_pendiente(
        pedido,
        "Quilmes Oeste SE LOGISTICA. Horarios para retirar?",
    )

    assert ok is True
    assert MARCA_HORARIOS_RETIRO in pedido.ia_resumen
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
    assert pedido.ia_requiere_operador is True
