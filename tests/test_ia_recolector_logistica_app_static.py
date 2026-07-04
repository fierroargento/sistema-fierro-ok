from pathlib import Path


def extraer_funcion(nombre):
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index(f"def {nombre}")
    fin = texto.find("\ndef ", inicio + 1)
    if fin == -1:
        fin = len(texto)
    return texto[inicio:fin]


def test_guardar_resultado_usa_service_reencauce_logistico():
    bloque = extraer_funcion("ia_guardar_resultado_recolector")

    assert "debe_reencauzar_pp6040_sin_faltantes_service" in bloque
    assert "services.ia_recolector_logistica" in bloque
    assert "reencauzado a logística automática PP6040 sin faltantes reales" in bloque
    assert "requiere_operador_final = False" in bloque

    pos_resolver = bloque.index("resolver_requiere_operador_final_recolector")
    pos_service = bloque.index("debe_reencauzar_pp6040_sin_faltantes_service")
    pos_estado = bloque.index("estado = decidir_estado_recolector")

    assert pos_resolver < pos_service < pos_estado
