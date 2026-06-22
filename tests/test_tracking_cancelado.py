from services.tracking_externo import interpretar_estado_logistico


def test_tracking_cancelada_se_clasifica_como_cancelado():
    assert interpretar_estado_logistico("CANCELADA", transporte="Correo Argentino") == "cancelado"


def test_tracking_cancelado_se_clasifica_como_cancelado():
    assert interpretar_estado_logistico("ENVIO CANCELADO", transporte="Correo Argentino") == "cancelado"


def test_tracking_devolucion_sigue_siendo_incidencia():
    assert interpretar_estado_logistico("DEVOLUCION AL REMITENTE", transporte="Correo Argentino") == "incidencia"
