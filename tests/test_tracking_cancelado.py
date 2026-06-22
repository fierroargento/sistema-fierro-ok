from services.tracking_externo import interpretar_estado_logistico


def test_tracking_cancelada_se_clasifica_como_cancelado():
    assert interpretar_estado_logistico("CANCELADA", transporte="Correo Argentino") == "cancelado"


def test_tracking_cancelado_se_clasifica_como_cancelado():
    assert interpretar_estado_logistico("ENVIO CANCELADO", transporte="Correo Argentino") == "cancelado"


def test_tracking_devolucion_sigue_siendo_incidencia():
    assert interpretar_estado_logistico("DEVOLUCION AL REMITENTE", transporte="Correo Argentino") == "incidencia"


def test_correo_extrae_cancelada_antes_que_preimposicion():
    from services.tracking_externo import _extraer_estado_por_patrones

    texto = """
    Fecha Planta Historia Estado
    19-06-2026 16:20 CORREO ARGENTINO CANCELADA
    19-06-2026 14:18 CORREO ARGENTINO PREIMPOSICION
    """

    estado = _extraer_estado_por_patrones(texto, transporte="Correo Argentino")

    assert "CANCELADA" in estado.upper()
