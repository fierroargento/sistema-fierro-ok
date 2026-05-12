"""
tests/test_ownership_canales.py
──────────────────────────────
Tests APB sobre ownership entre canales.
"""

from tests.fixtures.pedido_factory import PedidoFake

from services.canal_manager import (
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