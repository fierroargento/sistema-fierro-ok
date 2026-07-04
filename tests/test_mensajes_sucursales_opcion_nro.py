from services.mensajes_sucursales import (
    extraer_opcion_sucursal_explicita,
    normalizar_numero_opcion_sucursal,
    seleccionar_sucursal_ofrecida_por_opcion,
)


def test_sucursal_nro_2_se_normaliza_como_segunda_opcion():
    assert normalizar_numero_opcion_sucursal("Sucursal Nro 2") == 1
    assert extraer_opcion_sucursal_explicita("Sucursal Nro 2", cantidad_opciones=2) == 1


def test_variantes_sucursal_numero_2():
    ejemplos = [
        "sucursal nro 2",
        "sucursal numero 2",
        "suc nro 2",
        "nro 2",
        "opcion 2",
        "la 2",
    ]

    for texto in ejemplos:
        assert extraer_opcion_sucursal_explicita(texto, cantidad_opciones=3) == 1


def test_selecciona_sucursal_ofrecida_por_indice_e_id():
    sucursales = [
        {"id": "A1", "nombre": "Agencia Formosa"},
        {"id": "B2", "nombre": "Terminal Formosa"},
    ]

    assert seleccionar_sucursal_ofrecida_por_opcion(
        sucursales,
        ["A1", "B2"],
        1,
    ) == {"id": "B2", "nombre": "Terminal Formosa"}


def test_no_selecciona_indice_fuera_de_rango():
    sucursales = [{"id": "A1", "nombre": "Agencia Formosa"}]

    assert seleccionar_sucursal_ofrecida_por_opcion(sucursales, ["A1"], 2) is None
