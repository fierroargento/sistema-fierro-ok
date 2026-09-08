from pathlib import Path

import pytest

from services.whatsapp_idempotencia import ya_existe_mensaje_operador_reciente


class PedidoFake:
    id = 31
    organizacion_id = None


def test_idempotencia_rechaza_pedido_sin_tenant():
    with pytest.raises(ValueError, match="organización"):
        ya_existe_mensaje_operador_reciente(object(), PedidoFake(), "Hola")


def test_consulta_exige_organizacion_en_codigo():
    fuente = Path("services/whatsapp_idempotencia.py").read_text(
        encoding="utf-8-sig"
    )
    assert 'getattr(pedido, "organizacion_id", None)' in fuente
    assert "WhatsAppMensaje.organizacion_id == organizacion_id" in fuente
