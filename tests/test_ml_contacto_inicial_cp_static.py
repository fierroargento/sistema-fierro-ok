from pathlib import Path


def texto_contacto():
    return Path("modules/bot_ml/contacto.py").read_text(encoding="utf-8")


def test_contacto_inicial_pp6040_pide_cp_y_localidad():
    texto = texto_contacto()

    inicio = texto.index("if pedido_es_plegable_pp6040(pedido):")
    fin = texto.index("else:", inicio)
    bloque = texto[inicio:fin]

    assert "- Direccion completa\\n" in bloque
    assert "- Localidad\\n" in bloque
    assert "- Codigo postal\\n" in bloque
    assert "- Telefono de contacto\\n" in bloque


def test_contacto_inicial_via_cargo_pide_cp_y_localidad():
    texto = texto_contacto()

    inicio = texto.index("else:")
    fin = texto.index("if len(texto) > 348:", inicio)
    bloque = texto[inicio:fin]

    assert "- Direccion completa\\n" in bloque
    assert "- Localidad\\n" in bloque
    assert "- Codigo postal\\n" in bloque
    assert "- Telefono\\n" in bloque
