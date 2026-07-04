from types import SimpleNamespace

from services.canal_manager import puede_enviar_mensaje


def test_ml_no_bloquea_si_falta_elegir_sucursal_correo():
    pedido = SimpleNamespace(
        wa_estado="falta_elegir_transporte",
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        correo_sucursales_ofrecidas='[{"nombre": "Sucursal 1"}]',
        ia_sucursales_ofrecidas=None,
        ultimo_mensaje_automatico_texto="",
        ultimo_mensaje_automatico_canal="",
        ultimo_mensaje_automatico_fecha=None,
    )

    puede, motivo = puede_enviar_mensaje(
        pedido,
        "ml",
        "Te paso las opciones más cercanas...",
    )

    assert puede is True
    assert motivo == "OK"


def test_ml_sigue_bloqueado_si_whatsapp_tiene_operador_manual():
    pedido = SimpleNamespace(
        wa_estado="operador_manual",
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        correo_sucursales_ofrecidas='[{"nombre": "Sucursal 1"}]',
        ia_sucursales_ofrecidas=None,
        ultimo_mensaje_automatico_texto="",
        ultimo_mensaje_automatico_canal="",
        ultimo_mensaje_automatico_fecha=None,
    )

    puede, motivo = puede_enviar_mensaje(
        pedido,
        "ml",
        "Mensaje automático",
    )

    assert puede is False
    assert "WhatsApp activo" in motivo


def test_ml_sigue_bloqueado_si_no_hay_sucursales_ofrecidas():
    pedido = SimpleNamespace(
        wa_estado="falta_elegir_transporte",
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        correo_sucursales_ofrecidas=None,
        ia_sucursales_ofrecidas=None,
        ultimo_mensaje_automatico_texto="",
        ultimo_mensaje_automatico_canal="",
        ultimo_mensaje_automatico_fecha=None,
    )

    puede, motivo = puede_enviar_mensaje(
        pedido,
        "ml",
        "Mensaje automático",
    )

    assert puede is False
    assert "WhatsApp activo" in motivo
