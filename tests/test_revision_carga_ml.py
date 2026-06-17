from services.revision_carga_ml import (
    detectar_revision_carga_por_mensaje_ml,
    marcar_revision_carga_por_mensaje_ml,
)


class PedidoFake:
    agregado_pendiente_revision = False
    agregado_revision_fecha = "algo"
    agregado_revision_usuario = "usuario"
    ml_mensajes_pendientes = False
    ml_mensajes_pendientes_count = 0
    ia_requiere_operador = False
    ia_resumen = ""


def test_detecta_pedido_de_manijas():
    assert detectar_revision_carga_por_mensaje_ml(
        "Hola, quiero que le pongan manijas a la parrilla"
    ) is True


def test_detecta_modificacion_de_patas():
    assert detectar_revision_carga_por_mensaje_ml(
        "Se puede agregar patas más altas?"
    ) is True


def test_no_detecta_codigo_postal_simple():
    assert detectar_revision_carga_por_mensaje_ml("2761") is False


def test_no_detecta_datos_logisticos_normales():
    assert detectar_revision_carga_por_mensaje_ml(
        "Mi DNI es 30111222 y la dirección es San Martín 123"
    ) is False


def test_marcar_revision_carga_setea_flags():
    pedido = PedidoFake()

    ok = marcar_revision_carga_por_mensaje_ml(
        pedido,
        "Quiero que le agreguen manijas",
    )

    assert ok is True
    assert pedido.agregado_pendiente_revision is True
    assert pedido.agregado_revision_fecha is None
    assert pedido.agregado_revision_usuario is None
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
    assert pedido.ia_requiere_operador is True
    assert "ML requiere revisión de Carga" in pedido.ia_resumen


def test_marcar_revision_carga_no_marca_si_no_corresponde():
    pedido = PedidoFake()

    ok = marcar_revision_carga_por_mensaje_ml(
        pedido,
        "Hola, mi código postal es 2761",
    )

    assert ok is False
    assert pedido.agregado_pendiente_revision is False
