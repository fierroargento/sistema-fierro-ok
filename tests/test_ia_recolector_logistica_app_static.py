from pathlib import Path
import ast


def extraer_funcion(ruta, nombre):
    texto = Path(ruta).read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    nodo = next(
        item
        for item in arbol.body
        if isinstance(item, ast.FunctionDef)
        and item.name == nombre
    )
    lineas = texto.splitlines()
    return "\n".join(
        lineas[nodo.lineno - 1:nodo.end_lineno]
    )


def test_aplicador_usa_service_reencauce_logistico():
    bloque = extraer_funcion(
        "services/ia_recolector_resultado.py",
        "aplicar_resultado_recolector",
    )

    assert (
        "debe_reencauzar_pp6040_"
        "sin_faltantes_service"
        in bloque
    )
    assert (
        "resolver_requiere_operador_"
        "final_recolector"
        in bloque
    )
    assert (
        "requiere_operador_final = False"
        in bloque
    )

    pos_resolver = bloque.index(
        "resolver_requiere_operador_"
        "final_recolector"
    )
    pos_reencauce = bloque.index(
        "debe_reencauzar_pp6040_"
        "sin_faltantes_service"
    )

    assert pos_resolver < pos_reencauce


def test_app_delega_aplicacion_y_solo_ejecuta_handoff():
    bloque = extraer_funcion(
        "app.py",
        "ia_guardar_resultado_recolector",
    )

    assert "aplicar_resultado_recolector(" in bloque
    assert (
        "if resultado_aplicacion.iniciar_handoff:"
        in bloque
    )
    assert (
        "wa_auto_iniciar_desde_ml_si_corresponde("
        in bloque
    )
    assert (
        "resultado_aplicacion.faltantes"
        in bloque
    )

    assert "json.dumps(" not in bloque
    assert (
        "decidir_estado_recolector("
        not in bloque
    )
    assert (
        "debe_reencauzar_pp6040_"
        "sin_faltantes_service("
        not in bloque
    )
    assert "db.session" not in bloque
