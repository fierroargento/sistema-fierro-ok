from modules.whatsapp.text_utils import (
    es_afirmativo,
    es_negativo,
    pregunta_precio,
    pregunta_cantidad,
    es_queja_o_problema,
    es_consulta_factura,
    requiere_factura_distinta,
)


def test_es_afirmativo_detecta_respuestas_positivas():
    assert es_afirmativo("sí, perfecto")
    assert es_afirmativo("dale")
    assert es_afirmativo("confirmado")


def test_es_negativo_detecta_respuestas_negativas():
    assert es_negativo("no gracias")
    assert es_negativo("prefiero domicilio")
    assert es_negativo("por ahora no")


def test_pregunta_precio_detecta_consulta_de_precio():
    assert pregunta_precio("cuánto sale?")
    assert pregunta_precio("precio?")
    assert pregunta_precio("costo del envío")


def test_pregunta_cantidad_extrae_numero():
    assert pregunta_cantidad("quiero 3 unidades") == 3
    assert pregunta_cantidad("necesito 12") == 12
    assert pregunta_cantidad("sin cantidad") is None


def test_es_queja_o_problema_detecta_reclamos():
    assert es_queja_o_problema("no llegó")
    assert es_queja_o_problema("quiero hacer un reclamo")
    assert es_queja_o_problema("vino roto")


def test_es_consulta_factura_detecta_facturacion():
    assert es_consulta_factura("hacen factura A?")
    assert es_consulta_factura("necesito facturación")


def test_requiere_factura_distinta_detecta_datos_distintos():
    assert requiere_factura_distinta("te paso los datos")
    assert requiere_factura_distinta("con otro CUIT")
    assert requiere_factura_distinta("a nombre de otra razón social")


def test_es_afirmativo_detecta_queda_bien():
    from modules.whatsapp.text_utils import es_afirmativo

    assert es_afirmativo("me queda bien") is True
    assert es_afirmativo("le queda bien") is True
    assert es_afirmativo("queda bien") is True
