from app import (
    ia_extraer_datos_clasico_fierro,
    ia_texto_menciona_autorizado
)

def test_extractor_cp_solo_numero():
    texto = "3500"

    resultado = ia_extraer_datos_clasico_fierro(
        texto_cliente=texto,
        datos_previos={}
    )

    assert resultado.get("codigo_postal") == "3500"
    
def test_detecta_autorizado():
    texto = "Puede retirar Juan Perez"

    resultado = ia_texto_menciona_autorizado(texto)

    assert resultado is True    