from pathlib import Path


def texto_app():
    return Path("app.py").read_text(encoding="utf-8")


def extraer_funcion(nombre):
    texto = texto_app()
    inicio = texto.index(f"def {nombre}")
    fin = texto.find("\ndef ", inicio + 1)
    if fin == -1:
        fin = len(texto)
    return texto[inicio:fin]


def bloque_post_analisis():
    return extraer_funcion("ia_auto_responder_post_analisis")


def bloque_wa_auto():
    return extraer_funcion("wa_auto_iniciar_desde_ml_si_corresponde")


def test_demora_simple_no_dispara_handoff_si_falta_sucursal_ml():
    bloque = bloque_post_analisis()

    assert "debe_priorizar_sucursal_ml = bool(" in bloque
    assert "pedido_es_plegable_pp6040(pedido)" in bloque
    assert "ml_acordas_via_cargo_bloquea_inicio_wa(pedido)" in bloque
    assert "correo_sucursales_ofrecidas" in bloque

    condicion = '''if (
        not faltantes
        and detectar_consulta_demora_simple_ml(pedido)
        and not debe_priorizar_sucursal_ml
    ):'''
    assert condicion in bloque


def test_wa_auto_no_inicia_si_ml_debe_cerrar_sucursal():
    bloque = bloque_wa_auto()

    assert "ML debe cerrar elección de sucursal antes de WhatsApp" in bloque
    assert 'return False, "ml_debe_cerrar_sucursal"' in bloque
    assert "pedido_es_plegable_pp6040(pedido)" in bloque
    assert "correo_sucursales_ofrecidas" in bloque

    pos_guard = bloque.index("ML debe cerrar elección de sucursal antes de WhatsApp")
    pos_faltantes = bloque.index("if faltantes_limpios:")

    assert pos_guard < pos_faltantes
