from services.ml_consultas_logisticas import (
    detectar_consulta_demora_simple_ml,
    limpiar_derivacion_operador_por_demora_simple,
    texto_demora_handoff_wa_ml,
)


class PedidoFake:
    def __init__(
        self,
        ia_resumen="",
        ia_requiere_operador=False,
        ia_recolector_estado="",
    ):
        self.ia_resumen = ia_resumen
        self.ia_requiere_operador = ia_requiere_operador
        self.ia_recolector_estado = ia_recolector_estado


def test_detecta_pregunta_por_demora_simple_aunque_haya_marca_sin_cobertura():
    pedido = PedidoFake(
        ia_resumen="Pregunta por demora | Sin cobertura transportes CP 2900",
    )

    assert detectar_consulta_demora_simple_ml(pedido) is True


def test_no_detecta_como_simple_si_es_reclamo_por_demora():
    pedido = PedidoFake(
        ia_resumen="Cliente hace reclamo por demora y está enojado",
    )

    assert detectar_consulta_demora_simple_ml(pedido) is False


def test_limpia_requiere_operador_si_la_demora_es_simple():
    pedido = PedidoFake(
        ia_resumen="Pregunta por demora | Sin cobertura transportes CP 2900",
        ia_requiere_operador=True,
        ia_recolector_estado="requiere_operador",
    )

    assert limpiar_derivacion_operador_por_demora_simple(pedido) is True
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_recolector_estado == "datos_completos"


def test_texto_demora_informa_plazo_y_transicion_a_whatsapp():
    texto = texto_demora_handoff_wa_ml()

    assert "3 y 5 días hábiles" in texto
    assert "a partir del despacho" in texto
    assert "WhatsApp" in texto
