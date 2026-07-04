from types import SimpleNamespace

from services.transporte_revision import limpiar_revision_correo_resuelta_por_sucursales


def test_limpia_revision_correo_si_ya_hay_sucursales_ofrecidas():
    pedido = SimpleNamespace(
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
        correo_sucursales_ofrecidas="[1,2,3]",
        ia_resumen=(
            "TRANSPORTE: No se pudo cotizar Correo para CP 1564. "
            "Revisar respuesta de la integración"
        ),
        ia_requiere_operador=True,
        ml_mensajes_pendientes=True,
        ml_mensajes_pendientes_count=1,
    )

    ok = limpiar_revision_correo_resuelta_por_sucursales(pedido)

    assert ok is True
    assert "No se pudo cotizar Correo" not in pedido.ia_resumen
    assert pedido.ia_requiere_operador is False
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0


def test_no_limpia_otro_pendiente_operador():
    pedido = SimpleNamespace(
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        sucursal_nombre="QUILMES OESTE SE LOGISTICA",
        correo_sucursales_ofrecidas="[1,2,3]",
        ia_resumen=(
            "TRANSPORTE: No se pudo cotizar Correo para CP 1564 | "
            "Cliente consultó horarios de retiro/atención de la sucursal"
        ),
        ia_requiere_operador=True,
        ml_mensajes_pendientes=True,
        ml_mensajes_pendientes_count=1,
    )

    ok = limpiar_revision_correo_resuelta_por_sucursales(pedido)

    assert ok is True
    assert "No se pudo cotizar Correo" not in pedido.ia_resumen
    assert "horarios" in pedido.ia_resumen
    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
