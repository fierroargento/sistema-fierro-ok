from types import SimpleNamespace

from services.motor_bloqueo import (
    cantidad_pp6040_pedido,
    validar_datos_basicos,
    validar_datos_entrega,
    validar_datos_ml,
    validar_regla_via_cargo_pp6040,
    validar_transporte_obligatorio,
    validar_transportes,
    via_cargo_no_permitido_para_pp6040,
)


def item(sku="", descripcion="", cantidad=1):
    return SimpleNamespace(
        sku=sku,
        descripcion=descripcion,
        cantidad=cantidad,
    )


def pedido_base(**overrides):
    datos = {
        "cliente": "Cliente Test",
        "canal": "Presencial",
        "items": [item("SKU1", "Producto test", 1)],
        "empresa_envio": "Andreani",
        "tipo_entrega": "Domicilio",
        "direccion": "Calle 123",
        "codigo_postal": "8500",
        "localidad": "Viedma",
        "provincia": "Rio Negro",
        "seguimiento": "ABC123",
        "etiqueta_archivo": "etiqueta.pdf",
        "ml_tipo": "",
        "ml_buyer_nickname": "",
        "ml_billing_nombre": "",
        "ml_billing_documento": "",
        "dni": "12345678",
        "telefono": "+5492920123456",
        "sucursal_nombre": "",
        "autorizado_nombre": "",
        "autorizado_dni": "",
        "autorizado_telefono": "",
    }
    datos.update(overrides)
    return SimpleNamespace(**datos)


def test_validar_datos_basicos_detecta_faltantes():
    pedido = pedido_base(cliente="", canal="", items=[])

    errores = validar_datos_basicos(pedido)

    assert "Falta cliente." in errores
    assert "Falta canal." in errores
    assert "No hay productos cargados." in errores


def test_validar_datos_ml_mercado_envios_requiere_seguimiento_y_etiqueta():
    pedido = pedido_base(
        canal="Mercado Libre",
        ml_tipo="Mercado Envíos",
        seguimiento="",
        etiqueta_archivo="",
    )

    errores = validar_datos_ml(
        pedido,
        parece_nickname_ml=lambda cliente, nickname: False,
    )

    assert "Falta seguimiento ML." in errores
    assert "Falta adjuntar etiqueta." in errores


def test_validar_datos_ml_acordas_requiere_datos_cliente():
    pedido = pedido_base(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        cliente="comprador_test",
        ml_buyer_nickname="comprador_test",
        ml_billing_nombre="",
        dni="",
        ml_billing_documento="",
        telefono="",
    )

    errores = validar_datos_ml(
        pedido,
        parece_nickname_ml=lambda cliente, nickname: True,
    )

    assert "Falta nombre real del cliente." in errores
    assert "Falta DNI/CUIT del cliente." in errores
    assert "Falta teléfono del cliente." in errores


def test_validar_datos_entrega_domicilio_incompleto():
    pedido = pedido_base(
        tipo_entrega="Domicilio",
        direccion="",
        codigo_postal="",
        localidad="",
        provincia="",
    )

    errores = validar_datos_entrega(pedido)

    assert "Faltan datos domicilio." in errores
    assert "Falta CP." in errores


def test_validar_datos_entrega_sucursal_con_autorizado_incompleto():
    pedido = pedido_base(
        tipo_entrega="Sucursal",
        sucursal_nombre="Sucursal Centro",
        direccion="Sucursal 123",
        localidad="Viedma",
        provincia="Rio Negro",
        autorizado_nombre="Pedro",
        autorizado_dni="",
        autorizado_telefono="",
    )

    errores = validar_datos_entrega(pedido)

    assert "Falta DNI del autorizado." in errores
    assert "Falta teléfono del autorizado." in errores


def test_validar_transportes_andreani_requiere_seguimiento_y_etiqueta():
    pedido = pedido_base(
        empresa_envio="Andreani",
        seguimiento="",
        etiqueta_archivo="",
    )

    errores = validar_transportes(
        pedido,
        es_tnube=lambda p: False,
    )

    assert "Falta número de seguimiento." in errores
    assert "Falta adjuntar etiqueta." in errores


def test_validar_transporte_obligatorio_sin_transporte_agrega_error():
    pedido = pedido_base(
        empresa_envio="",
    )

    errores = validar_transporte_obligatorio(
        pedido,
        usa_flujo_etiqueta_directa=lambda p: False,
    )

    assert "Falta transporte." in errores


def test_cantidad_pp6040_pedido_suma_solo_por_sku():
    pedido = pedido_base(
        items=[
            item(sku="PP6040H", descripcion="", cantidad=1),
            item(sku="", descripcion="Parrilla PP6040 reforzada", cantidad=2),
        ]
    )

    assert cantidad_pp6040_pedido(pedido) == 1


def test_pp6040_via_cargo_bloquea_con_una_o_dos_unidades():
    pedido = pedido_base(
        empresa_envio="Vía Cargo",
        items=[item(sku="PP6040H", cantidad=2)],
    )

    assert via_cargo_no_permitido_para_pp6040(pedido) is True
    assert validar_regla_via_cargo_pp6040(pedido)


def test_pp6040_via_cargo_permite_con_tres_unidades():
    pedido = pedido_base(
        empresa_envio="Vía Cargo",
        items=[item(sku="PP6040H", cantidad=3)],
    )

    assert via_cargo_no_permitido_para_pp6040(pedido) is False
    assert validar_regla_via_cargo_pp6040(pedido) is None