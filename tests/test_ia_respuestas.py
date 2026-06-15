from services.ia_respuestas import (
    agregar_marca_resumen_unica_service,
    detectar_contexto_resumen_faltantes_service,
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

def test_detectar_contexto_resumen_faltantes_service_sin_contexto():
    resultado = detectar_contexto_resumen_faltantes_service("cliente pasó nombre y dni")

    assert resultado == {
        "resumen_ml_explicito": False,
        "pregunta_por_que": False,
        "pregunta_costo_envio": False,
        "pregunta_cuando_sale": False,
        "pregunta_cuanto_tarda": False,
        "cliente_dice_ya_los_pase": False,
        "pide_llamada_o_whatsapp": False,
        "hay_contexto_especial": False,
    }


def test_detectar_contexto_resumen_faltantes_service_detecta_ml_explicito():
    resultado = detectar_contexto_resumen_faltantes_service("el cliente dice que los datos ya están en Mercado Libre")

    assert resultado["resumen_ml_explicito"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_por_que():
    resultado = detectar_contexto_resumen_faltantes_service("el cliente pregunta por qué pedimos esos datos")

    assert resultado["pregunta_por_que"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_costo_envio():
    resultado = detectar_contexto_resumen_faltantes_service("pregunta cuánto sale el envío")

    assert resultado["pregunta_costo_envio"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_cuando_sale():
    resultado = detectar_contexto_resumen_faltantes_service("pregunta cuándo despachan la compra")

    assert resultado["pregunta_cuando_sale"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_cuanto_tarda():
    resultado = detectar_contexto_resumen_faltantes_service("pregunta cuánto tarda en llegar")

    assert resultado["pregunta_cuanto_tarda"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_ya_los_pase():
    resultado = detectar_contexto_resumen_faltantes_service("cliente dice ya los pasé")

    assert resultado["cliente_dice_ya_los_pase"] is True
    assert resultado["hay_contexto_especial"] is True


def test_detectar_contexto_resumen_faltantes_service_detecta_whatsapp():
    resultado = detectar_contexto_resumen_faltantes_service("cliente pide hablar por whatsapp")

    assert resultado["pide_llamada_o_whatsapp"] is True
    assert resultado["hay_contexto_especial"] is True
