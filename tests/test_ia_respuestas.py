from services.ia_respuestas import ia_etiqueta_faltante_service


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
