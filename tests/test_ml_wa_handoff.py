from services.ml_wa_handoff import (
    MARCA_TRANSICION_ML_WA,
    debe_avisar_transicion_ml_wa,
    marcar_transicion_ml_wa_en_resumen,
    ml_conversacion_cortada_para_handoff_wa_service,
    texto_transicion_ml_wa_datos_completos,
)


class PedidoFake:
    def __init__(self):
        self.ia_resumen = ""
        self.ia_ultimo_timeout_operador = None
        self.ia_requiere_operador = False
        self.ia_canal_activo = ""


class EstadoConversacionalFake:
    def __init__(
        self,
        canal_activo="ml",
        bot_pausado=False,
        takeover_activo=False,
    ):
        self.canal_activo = canal_activo
        self.bot_pausado = bot_pausado
        self.takeover_activo = takeover_activo


def test_debe_avisar_transicion_ml_wa_si_no_tiene_marca():
    pedido = PedidoFake()
    pedido.ia_resumen = "Datos completos"

    assert debe_avisar_transicion_ml_wa(pedido) is True


def test_debe_avisar_transicion_ml_wa_false_si_ya_tiene_marca():
    pedido = PedidoFake()
    pedido.ia_resumen = "Datos completos | ML avisó migración a WhatsApp"

    assert debe_avisar_transicion_ml_wa(pedido) is False


def test_marcar_transicion_ml_wa_en_resumen_agrega_marca_una_vez():
    pedido = PedidoFake()
    pedido.ia_resumen = "Datos completos"

    resumen = marcar_transicion_ml_wa_en_resumen(pedido)

    assert "ML avisó migración a WhatsApp" in resumen
    assert pedido.ia_resumen.count("ML avisó migración a WhatsApp") == 1

    marcar_transicion_ml_wa_en_resumen(pedido)

    assert pedido.ia_resumen.count("ML avisó migración a WhatsApp") == 1


def test_ml_conversacion_cortada_sin_pedido():
    assert ml_conversacion_cortada_para_handoff_wa_service(None) == (
        False,
        "sin_pedido",
    )


def test_ml_conversacion_cortada_por_timeout_registrado():
    pedido = PedidoFake()
    pedido.ia_ultimo_timeout_operador = "2026-01-01"

    assert ml_conversacion_cortada_para_handoff_wa_service(pedido) == (
        True,
        "timeout_ml_registrado",
    )


def test_ml_conversacion_cortada_por_requiere_operador():
    pedido = PedidoFake()
    pedido.ia_requiere_operador = True

    assert ml_conversacion_cortada_para_handoff_wa_service(pedido) == (
        True,
        "requiere_operador",
    )


def test_ml_conversacion_cortada_por_canal_ia_no_ml():
    pedido = PedidoFake()
    pedido.ia_canal_activo = "wa"

    assert ml_conversacion_cortada_para_handoff_wa_service(pedido) == (
        True,
        "canal_ia_no_ml:wa",
    )


def test_ml_conversacion_cortada_por_canal_conversacional_no_ml():
    pedido = PedidoFake()

    def obtener_estado(pedido, crear_si_no_existe=False):
        return EstadoConversacionalFake(canal_activo="wa")

    assert ml_conversacion_cortada_para_handoff_wa_service(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado,
    ) == (
        True,
        "canal_conversacional_no_ml:wa",
    )


def test_ml_conversacion_cortada_por_bot_pausado():
    pedido = PedidoFake()

    def obtener_estado(pedido, crear_si_no_existe=False):
        return EstadoConversacionalFake(bot_pausado=True)

    assert ml_conversacion_cortada_para_handoff_wa_service(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado,
    ) == (
        True,
        "bot_pausado",
    )


def test_ml_conversacion_cortada_por_takeover_operador():
    pedido = PedidoFake()

    def obtener_estado(pedido, crear_si_no_existe=False):
        return EstadoConversacionalFake(takeover_activo=True)

    assert ml_conversacion_cortada_para_handoff_wa_service(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado,
    ) == (
        True,
        "takeover_operador",
    )


def test_ml_conversacion_cortada_por_motivo_handoff():
    pedido = PedidoFake()

    assert ml_conversacion_cortada_para_handoff_wa_service(
        pedido,
        motivo_handoff="fallo_ml_envio",
    ) == (
        True,
        "motivo_handoff:fallo_ml_envio",
    )


def test_ml_conversacion_no_cortada_si_ml_sigue_activo():
    pedido = PedidoFake()

    def obtener_estado(pedido, crear_si_no_existe=False):
        return EstadoConversacionalFake(canal_activo="ml")

    assert ml_conversacion_cortada_para_handoff_wa_service(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado,
    ) == (
        False,
        "ml_activo_sigue_recolectando",
    )

def test_texto_transicion_ml_wa_datos_completos_agradece_y_avisa_whatsapp():
    texto = texto_transicion_ml_wa_datos_completos()

    assert "Gracias" in texto
    assert "datos necesarios" in texto
    assert "WhatsApp" in texto


def test_constante_marca_transicion_ml_wa_se_usa_en_resumen():
    pedido = PedidoFake()
    pedido.ia_resumen = f"Datos completos | {MARCA_TRANSICION_ML_WA}"

    assert debe_avisar_transicion_ml_wa(pedido) is False
