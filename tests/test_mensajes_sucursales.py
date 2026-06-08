from services.mensajes_sucursales import (
    armar_mensaje_sucursales,
    normalizar_numero_opcion_sucursal,
    texto_pide_opcion_numerica_sucursal,
)


def test_sin_sucursales_devuelve_none():
    assert armar_mensaje_sucursales([]) is None
    assert armar_mensaje_sucursales(None) is None


def test_una_sucursal_pide_confirmacion_no_eleccion():
    mensaje = armar_mensaje_sucursales([
        {
            "nombre": "Agencia Santa Fé",
            "direccion": "Gdor. Crespo Nro.2250",
        }
    ])

    assert "Encontré esta sucursal disponible" in mensaje
    assert "Confirmame si te queda bien" in mensaje
    assert "Decime el número" not in mensaje
    assert "Agencia Santa Fé" in mensaje
    assert "Gdor. Crespo Nro.2250" in mensaje


def test_varias_sucursales_pide_numero():
    mensaje = armar_mensaje_sucursales([
        {
            "nombre": "Agencia Santa Fé",
            "direccion": "Gdor. Crespo Nro.2250",
        },
        {
            "nombre": "Terminal Santa Fe",
            "direccion": "Belgrano 1234",
        },
    ])

    assert "Te paso sucursales cercanas" in mensaje
    assert "Decime el número" in mensaje
    assert "1) Agencia Santa Fé" in mensaje
    assert "2) Terminal Santa Fe" in mensaje
    assert "Confirmame si te queda bien" not in mensaje


def test_normaliza_numeros_y_palabras():
    assert normalizar_numero_opcion_sucursal("1") == 0
    assert normalizar_numero_opcion_sucursal("uno") == 0
    assert normalizar_numero_opcion_sucursal("una") == 0
    assert normalizar_numero_opcion_sucursal("la uno") == 0
    assert normalizar_numero_opcion_sucursal("2") == 1
    assert normalizar_numero_opcion_sucursal("dos") == 1
    assert normalizar_numero_opcion_sucursal("segunda") == 1
    assert normalizar_numero_opcion_sucursal("3") == 2
    assert normalizar_numero_opcion_sucursal("tres") == 2
    assert normalizar_numero_opcion_sucursal("tercera") == 2


def test_no_normaliza_texto_ambiguo():
    assert normalizar_numero_opcion_sucursal("si") is None
    assert normalizar_numero_opcion_sucursal("dale") is None
    assert normalizar_numero_opcion_sucursal("cualquiera") is None


def test_texto_pedir_opcion_numerica():
    mensaje = texto_pide_opcion_numerica_sucursal()

    assert "número" in mensaje
    assert "sucursal" in mensaje