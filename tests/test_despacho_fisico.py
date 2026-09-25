from datetime import datetime

from services.despacho_fisico import (
    confirmar_despacho_fisico,
    es_mercado_envios_correo,
    marcar_impuesto_sin_despacho,
    puede_marcar_impuesto_sin_despacho,
    tiene_despacho_fisico_pendiente,
)
from tests.fixtures.pedido_factory import PedidoFake, pedido_ml_mercado_envios


def test_solo_mercado_envios_embalado_admite_impuesto_sin_despacho():
    pedido = pedido_ml_mercado_envios(estado="Embalado")

    assert es_mercado_envios_correo(pedido) is True
    assert puede_marcar_impuesto_sin_despacho(pedido) is True

    assert puede_marcar_impuesto_sin_despacho(
        PedidoFake(canal="Tienda Nube", ml_tipo="", estado="Embalado")
    ) is False


def test_marcar_impuesto_crea_pendiente_fisico_sin_inventar_despacho_fisico():
    fecha = datetime(2026, 9, 25, 13, 30)
    pedido = pedido_ml_mercado_envios(estado="Embalado")

    ok, _ = marcar_impuesto_sin_despacho(
        pedido,
        usuario="franco",
        fecha=fecha,
    )

    assert ok is True
    assert pedido.impuesto_sin_despacho is True
    assert pedido.impuesto_sin_despacho_fecha == fecha
    assert pedido.impuesto_sin_despacho_usuario == "franco"
    assert pedido.despacho_fisico_fecha is None
    assert tiene_despacho_fisico_pendiente(pedido) is True


def test_webhook_o_estado_posterior_no_borra_flag_y_confirmacion_manual_lo_cierra():
    fecha_impuesto = datetime(2026, 9, 25, 13, 30)
    fecha_fisico = datetime(2026, 9, 26, 12, 0)
    pedido = pedido_ml_mercado_envios(
        estado="Finalizado",
        impuesto_sin_despacho=True,
        impuesto_sin_despacho_fecha=fecha_impuesto,
        impuesto_sin_despacho_usuario="franco",
    )

    assert tiene_despacho_fisico_pendiente(pedido) is True

    ok, _ = confirmar_despacho_fisico(
        pedido,
        usuario="maxi",
        fecha=fecha_fisico,
    )

    assert ok is True
    assert pedido.estado == "Finalizado"
    assert pedido.impuesto_sin_despacho is False
    assert pedido.despacho_fisico_fecha == fecha_fisico
    assert pedido.despacho_fisico_usuario == "maxi"
