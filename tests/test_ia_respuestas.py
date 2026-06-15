from services.ia_respuestas import (
    agregar_marca_resumen_unica_service,
    ia_etiqueta_faltante_service,
)


def test_ia_etiqueta_faltante_service_campos_conocidos():
    assert ia_etiqueta_faltante_service("nombre") == "Nombre"
    assert ia_etiqueta_faltante_service("apellido") == "Apellido"
    assert ia_etiqueta_faltante_service("dni") == "DNI"
    assert ia_etiqueta_faltante_service("telefono") == "Teléfono"
    assert ia_etiqueta_faltante_service("direccion") == "Dirección completa"
    assert ia_etiqueta_faltante_service("localidad") == "Localidad"
    assert ia_etiqueta_faltante_service("codigo_postal") == "Código postal"


def test_ia_etiqueta_faltante_service_campo_desconocido_capitaliza_y_reemplaza_guion_bajo():
    assert ia_etiqueta_faltante_service("nombre_autorizado") == "Nombre autorizado"


def test_ia_etiqueta_faltante_service_valor_vacio():
    assert ia_etiqueta_faltante_service("") == ""
    assert ia_etiqueta_faltante_service(None) == ""

def test_agregar_marca_resumen_unica_service_agrega_si_no_existe():
    resultado = agregar_marca_resumen_unica_service(
        "IA autocompletó dni",
        "Sin cobertura transportes CP 6070",
    )

    assert resultado == "IA autocompletó dni | Sin cobertura transportes CP 6070"


def test_agregar_marca_resumen_unica_service_no_duplica_si_ya_existe():
    resumen = "IA autocompletó dni | Sin cobertura transportes CP 6070"

    resultado = agregar_marca_resumen_unica_service(
        resumen,
        "Sin cobertura transportes CP 6070",
    )

    assert resultado == resumen


def test_agregar_marca_resumen_unica_service_respeta_limite():
    resultado = agregar_marca_resumen_unica_service(
        "abc",
        "marca larga",
        limite=5,
    )

    assert resultado == "abc |"
