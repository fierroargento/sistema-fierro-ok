from app import siguiente_estado


def test_flujo_embalado():
    resultado = siguiente_estado("Embalado")

    assert resultado == "Despachado"


def test_flujo_etiqueta_impresa():
    resultado = siguiente_estado("Etiqueta Impresa")

    assert resultado == "Embalado"