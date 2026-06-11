from services.mensajes_sucursales import extraer_opcion_sucursal_explicita


def test_extraer_opcion_sucursal_explicita_detecta_numero_en_texto_mixto():
    texto = "buen día, sucede 1. Llegará para el día del padre???"

    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=2) == 0


def test_extraer_opcion_sucursal_explicita_detecta_la_primera():
    texto = "elijo la primera"

    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=2) == 0


def test_extraer_opcion_sucursal_explicita_no_inventa_si_no_hay_numero():
    texto = "llegará para el día del padre?"

    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=2) is None


def test_extraer_opcion_sucursal_explicita_no_acepta_fuera_de_rango():
    texto = "elijo la 3"

    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=2) is None


def test_extraer_opcion_sucursal_explicita_no_acepta_multiples_opciones():
    texto = "puede ser la 1 o la 2?"

    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=2) is None
