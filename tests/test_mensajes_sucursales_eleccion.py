from services.mensajes_sucursales import (
    normalizar_numero_opcion_sucursal,
    extraer_opcion_sucursal_explicita,
)


def test_no_interpreta_tres_arroyos_como_opcion_tres():
    texto = "Lo más cerca es TRES ARROYOS"

    assert normalizar_numero_opcion_sucursal(texto) is None
    assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=3) is None


def test_interpreta_opcion_tres_cuando_es_explicita():
    assert normalizar_numero_opcion_sucursal("3") == 2
    assert normalizar_numero_opcion_sucursal("la 3") == 2
    assert normalizar_numero_opcion_sucursal("opción tres") == 2
    assert normalizar_numero_opcion_sucursal("tres") == 2

    assert extraer_opcion_sucursal_explicita("opción 3", cantidad_opciones=3) == 2
    assert extraer_opcion_sucursal_explicita("la tercera", cantidad_opciones=3) == 2


def test_no_interpreta_localidad_con_numero_en_palabras():
    assert extraer_opcion_sucursal_explicita("prefiero tres arroyos", cantidad_opciones=3) is None
    assert extraer_opcion_sucursal_explicita("soy de dos de mayo", cantidad_opciones=3) is None
