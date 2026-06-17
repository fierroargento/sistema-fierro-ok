from modules.whatsapp.text_utils import es_agradecimiento_simple


def test_detecta_gracias_simple_con_signos():
    assert es_agradecimiento_simple("gracias !!") is True


def test_detecta_ok_gracias():
    assert es_agradecimiento_simple("ok gracias") is True


def test_detecta_muchas_gracias():
    assert es_agradecimiento_simple("Muchas gracias!!!") is True


def test_no_detecta_consulta_con_gracias():
    assert es_agradecimiento_simple(
        "gracias, cuando llega el pedido?"
    ) is False


def test_no_detecta_problema_con_gracias():
    assert es_agradecimiento_simple(
        "gracias pero el producto vino roto"
    ) is False
