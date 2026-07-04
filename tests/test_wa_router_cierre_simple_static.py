from pathlib import Path


def test_router_evalua_cierre_simple_antes_de_escalar_listo_retirar():
    texto = Path("modules/whatsapp/router.py").read_text(encoding="utf-8")

    idx_estado = texto.index("if estado == WA_LISTO_PARA_RETIRAR")
    idx_cierre = texto.index("es_cierre_simple_retiro_post_aviso", idx_estado)
    idx_escalar = texto.index("_escalar_operador(", idx_estado)

    assert idx_estado < idx_cierre < idx_escalar
    assert "Cliente respondi" in texto[idx_estado:idx_escalar + 120]
