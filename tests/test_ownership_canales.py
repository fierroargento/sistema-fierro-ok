"""
tests/test_ownership_canales.py
──────────────────────────────
Tests APB sobre ownership entre canales.
"""

from tests.fixtures.pedido_factory import PedidoFake

from services.canal_manager import (
    ml_puede_gobernar_timeout,
    puede_enviar_mensaje,
    puede_hacer_handoff_ml_a_whatsapp,    
    wa_puede_gobernar_timeout,
)


class TestOwnershipCanales:

    def test_ml_activo_no_lo_gobierna_wa(self):
        """
        Si ML sigue siendo el canal activo,
        WA scheduler NO debe escalar.
        """

        pedido = PedidoFake(
            ia_canal_activo="mercadolibre",
            wa_estado="activo",
        )

        assert (
            wa_puede_gobernar_timeout(pedido)
            is False
        )

    def test_wa_activo_con_estado_wa_si_escalable(self):
        """
        Si WhatsApp es el canal activo
        y existe wa_estado real,
        WA scheduler sí gobierna timeout.
        """

        pedido = PedidoFake(
            ia_canal_activo="whatsapp",
            wa_estado="activo",
        )

        assert (
            wa_puede_gobernar_timeout(pedido)
            is True
        )

    def test_wa_sin_wa_estado_no_toma_ownership(self):
        """
        Protección APB:
        aunque diga whatsapp,
        si no existe wa_estado real,
        WA no toma ownership.
        """

        pedido = PedidoFake(
            ia_canal_activo="whatsapp",
            wa_estado="",
        )

        assert (
            wa_puede_gobernar_timeout(pedido)
            is False
        )

    def test_ml_con_wa_activo_no_gobierna_timeout(self):
        """
        Si WhatsApp ya tomó ownership,
        ML no debe gobernar timeout.
        """

        from services.canal_manager import (
            ml_puede_gobernar_timeout,
        )

        pedido = PedidoFake(
            wa_estado="activo",
        )

        assert (
            ml_puede_gobernar_timeout(pedido)
            is False
        )

    def test_ml_sin_wa_activo_si_gobierna_timeout(self):
        """
        Si WA no está activo,
        ML puede gobernar timeout.
        """

        from services.canal_manager import (
            ml_puede_gobernar_timeout,
        )

        pedido = PedidoFake(
            wa_estado="",
        )

        assert (
            ml_puede_gobernar_timeout(pedido)
            is True
        )

    def test_ml_no_puede_enviar_si_whatsapp_activo(self):
        """
        Si WhatsApp tomó ownership,
        ML no puede enviar mensajes automáticos.
        """

        pedido = PedidoFake(
            wa_estado="activo",
        )

        permitido, motivo = puede_enviar_mensaje(
            pedido=pedido,
            canal="ml",
            texto="Mensaje de prueba",
        )

        assert permitido is False
        assert "WhatsApp activo" in motivo

    def test_ml_puede_enviar_si_whatsapp_no_activo(self):
        """
        Si WhatsApp no tomó ownership,
        ML puede enviar mensaje automático.
        """

        pedido = PedidoFake(
            wa_estado="",
        )

        permitido, motivo = puede_enviar_mensaje(
            pedido=pedido,
            canal="ml",
            texto="Mensaje de prueba",
        )

        assert permitido is True
        assert motivo == "OK"

    def test_bloquea_mensaje_automatico_repetido(self):
        """
        Anti-duplicación:
        mismo canal + mismo texto debe bloquearse.
        """

        pedido = PedidoFake()

        pedido.ultimo_mensaje_automatico_canal = "ml"
        pedido.ultimo_mensaje_automatico_texto = "Hola cliente"

        permitido, motivo = puede_enviar_mensaje(
            pedido=pedido,
            canal="ml",
            texto="Hola cliente",
        )

        assert permitido is False
        assert motivo == "Mensaje automático repetido"
        
    def test_no_hace_handoff_si_wa_ya_iniciado(self):
        """
        APB:
        no debe pisar conversaciones
        WhatsApp existentes.
        """

        pedido = PedidoFake(
            wa_estado="activo",
        )

        permitido, motivo = (
            puede_hacer_handoff_ml_a_whatsapp(
                pedido
            )
        )

        assert permitido is False
        assert motivo == "wa_ya_iniciado"

    def test_no_hace_handoff_pedido_finalizado(self):
        """
        APB:
        pedidos cerrados no migran
        automáticamente a WhatsApp.
        """

        pedido = PedidoFake(
            estado="Finalizado",
        )

        permitido, motivo = (
            puede_hacer_handoff_ml_a_whatsapp(
                pedido
            )
        )

        assert permitido is False
        assert motivo == "pedido_cerrado"

    def test_handoff_valido(self):
        """
        Caso sano:
        puede migrar de ML a WhatsApp.
        """

        pedido = PedidoFake(
            wa_estado="",
            estado="Etiqueta Lista",
            ml_order_status="paid",
        )

        permitido, motivo = (
            puede_hacer_handoff_ml_a_whatsapp(
                pedido
            )
        )

        assert permitido is True
        assert motivo == "ok"        