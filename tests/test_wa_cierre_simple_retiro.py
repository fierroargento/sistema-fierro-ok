from modules.whatsapp.text_utils import es_cierre_simple_retiro_post_aviso


def test_cierre_simple_retiro_detecta_gracias_y_voy_a_buscarlo():
    assert es_cierre_simple_retiro_post_aviso("Bueno gracias, ahí voy a buscarlo") is True


def test_cierre_simple_retiro_detecta_paso_a_retirar():
    assert es_cierre_simple_retiro_post_aviso("Ok gracias, paso a retirar mañana") is True


def test_cierre_simple_retiro_no_toma_reclamo_como_cierre():
    assert es_cierre_simple_retiro_post_aviso("Gracias pero tengo un problema") is False


def test_cierre_simple_retiro_no_toma_consulta_compleja():
    assert es_cierre_simple_retiro_post_aviso("No puedo retirarlo, me cambiás la dirección?") is False
