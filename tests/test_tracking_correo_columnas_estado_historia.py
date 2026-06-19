from services.tracking_externo import (
    _extraer_estado_por_patrones,
    interpretar_estado_logistico,
)


def test_correo_intento_entrega_con_estado_en_espera_sucursal_clasifica_sucursal():
    texto = """
    Fecha Planta Historia Estado
    16-06-2026 12:36 JURE ACCESORIOS - ROLDAN INTENTO DE ENTREGA EN ESPERA EN SUCURSAL
    16-06-2026 08:53 ROLDAN EN PROCESO DE CLASIFICACIÓN
    """

    estado = _extraer_estado_por_patrones(texto, transporte="Correo Argentino")

    assert "INTENTO DE ENTREGA" in estado
    assert "EN ESPERA EN SUCURSAL" in estado
    assert interpretar_estado_logistico(estado, transporte="Correo Argentino") == "sucursal"


def test_correo_intento_entrega_sin_estado_sucursal_sigue_siendo_incidencia():
    texto = """
    Fecha Planta Historia Estado
    16-06-2026 12:36 JURE ACCESORIOS - ROLDAN INTENTO DE ENTREGA
    16-06-2026 08:53 ROLDAN EN PROCESO DE CLASIFICACIÓN
    """

    estado = _extraer_estado_por_patrones(texto, transporte="Correo Argentino")

    assert "INTENTO DE ENTREGA" in estado
    assert interpretar_estado_logistico(estado, transporte="Correo Argentino") == "incidencia"


def test_correo_intento_entrega_con_entrega_en_sucursal_clasifica_sucursal():
    texto = """
    Fecha Planta Historia Estado
    16-06-2026 12:36 JURE ACCESORIOS - ROLDAN INTENTO DE ENTREGA ENTREGA EN SUCURSAL
    16-06-2026 08:53 ROLDAN EN PROCESO DE CLASIFICACIÓN
    """

    estado = _extraer_estado_por_patrones(texto, transporte="Correo Argentino")

    assert "INTENTO DE ENTREGA" in estado
    assert "ENTREGA EN SUCURSAL" in estado
    assert interpretar_estado_logistico(estado, transporte="Correo Argentino") == "sucursal"
