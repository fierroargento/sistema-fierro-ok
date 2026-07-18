import ast
from pathlib import Path


def _bloque_wa_cerrar_datos_completos():
    texto = Path(
        "modules/whatsapp/flows_transporte.py"
    ).read_text(encoding="utf-8-sig")
    arbol = ast.parse(texto)
    lineas = texto.splitlines()

    funcion = next(
        nodo
        for nodo in arbol.body
        if isinstance(nodo, ast.FunctionDef)
        and nodo.name == "wa_cerrar_datos_completos"
    )

    return "\n".join(
        lineas[funcion.lineno - 1:funcion.end_lineno]
    )


def test_wa_correo_persiste_antes_de_enviar_oferta():
    bloque = _bloque_wa_cerrar_datos_completos()

    idx_preparar = bloque.index(
        "preparar_oferta_sucursales_correo_pedido("
    )
    idx_commit = bloque.index(
        "db.session.commit()",
        idx_preparar,
    )
    idx_enviar = bloque.index(
        "return wa_enviar_texto(",
        idx_commit,
    )

    assert idx_preparar < idx_commit < idx_enviar


def test_wa_correo_no_envia_si_falla_persistencia():
    bloque = _bloque_wa_cerrar_datos_completos()

    idx_resultado = bloque.index(
        "if resultado_suc.ok:"
    )
    idx_envio = bloque.index(
        "return wa_enviar_texto(",
        idx_resultado,
    )
    rama = bloque[idx_resultado:idx_envio]

    assert "except Exception as e:" in rama
    assert "db.session.rollback()" in rama
    assert "return False" in rama


def test_wa_correo_no_duplica_guardado_de_estado():
    bloque = _bloque_wa_cerrar_datos_completos()

    idx_resultado = bloque.index(
        "if resultado_suc.ok:"
    )
    idx_envio = bloque.index(
        "return wa_enviar_texto(",
        idx_resultado,
    )
    rama = bloque[idx_resultado:idx_envio]

    assert "_guardar_estado_wa(" not in rama
