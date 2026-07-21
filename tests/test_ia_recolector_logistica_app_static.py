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


def test_consumidores_delegan_al_workflow_sin_wrapper_en_app():
    app = Path("app.py").read_text(encoding="utf-8")
    flows = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")
    workflow = Path(
        "services/ia_recolector_workflow.py"
    ).read_text(encoding="utf-8")

    assert (
        "def ia_guardar_resultado_recolector("
        not in app
    )
    assert "aplicar_resultado_recolector(" not in app

    assert app.count(
        "procesar_resultado_recolector("
    ) == 1
    assert flows.count(
        "procesar_resultado_recolector("
    ) == 1

    assert (
        "from services.ia_recolector_workflow import ("
        in app
    )
    assert (
        "from services.ia_recolector_workflow import ("
        in flows
    )

    assert "aplicar_resultado_fn(" in workflow
    assert "if not aplicacion.iniciar_handoff:" in workflow
    assert "iniciar_handoff_fn(" in workflow

    assert "json.dumps(" not in app[
        app.index("procesar_resultado_recolector("):
        app.index(
            "orquestar_confirmacion_sucursal_comun_ml("
        )
    ]
