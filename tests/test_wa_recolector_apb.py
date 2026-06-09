from services.wa_recolector_apb import (
    cliente_cuestiona_pedido_de_datos,
    armar_mensaje_faltantes_recolector,
)


def test_cliente_cuestiona_pedido_de_datos_detecta_mercado_libre():
    texto = "Quería preguntar por qué me piden esto si ya está cargado en Mercado Libre"

    assert cliente_cuestiona_pedido_de_datos(texto) is True


def test_cliente_cuestiona_pedido_de_datos_detecta_ya_los_pase():
    texto = "Esos datos ya los pasé por la aplicación"

    assert cliente_cuestiona_pedido_de_datos(texto) is True


def test_cliente_cuestiona_pedido_de_datos_no_detecta_mensaje_normal():
    texto = "Mi DNI es 32333444"

    assert cliente_cuestiona_pedido_de_datos(texto) is False


def test_armar_mensaje_faltantes_recolector_con_explicacion():
    campos = {
        "dni": "DNI",
        "codigo_postal": "código postal",
    }

    mensaje = armar_mensaje_faltantes_recolector(
        ["dni"],
        campos,
        texto_cliente="Ya está cargado en Mercado Libre",
    )

    assert "Mercado Libre no siempre nos muestra" in mensaje
    assert "• DNI" in mensaje
    assert "código postal" not in mensaje


def test_armar_mensaje_faltantes_recolector_normal():
    campos = {
        "dni": "DNI",
    }

    mensaje = armar_mensaje_faltantes_recolector(
        ["dni"],
        campos,
        texto_cliente="Ok",
    )

    assert mensaje.startswith("Perfecto, gracias.")
    assert "• DNI" in mensaje
