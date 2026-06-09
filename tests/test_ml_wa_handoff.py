from services.ml_wa_handoff import (
    MARCA_TRANSICION_ML_WA,
    texto_transicion_ml_wa_datos_completos,
    debe_avisar_transicion_ml_wa,
    marcar_transicion_ml_wa_en_resumen,
)


class PedidoFake:
    def __init__(self, ia_resumen=""):
        self.ia_resumen = ia_resumen


def test_texto_transicion_ml_wa_datos_completos_agradece_y_avisa_whatsapp():
    texto = texto_transicion_ml_wa_datos_completos()

    assert "Gracias" in texto
    assert "datos necesarios" in texto
    assert "WhatsApp" in texto


def test_debe_avisar_transicion_ml_wa_si_no_tiene_marca():
    pedido = PedidoFake("Datos completos")

    assert debe_avisar_transicion_ml_wa(pedido) is True


def test_no_debe_avisar_transicion_ml_wa_si_ya_tiene_marca():
    pedido = PedidoFake(f"Datos completos | {MARCA_TRANSICION_ML_WA}")

    assert debe_avisar_transicion_ml_wa(pedido) is False


def test_marcar_transicion_ml_wa_en_resumen_no_duplica():
    pedido = PedidoFake(f"Datos completos | {MARCA_TRANSICION_ML_WA}")

    marcar_transicion_ml_wa_en_resumen(pedido)

    assert pedido.ia_resumen.count(MARCA_TRANSICION_ML_WA) == 1
