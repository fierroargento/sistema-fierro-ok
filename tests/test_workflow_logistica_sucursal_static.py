from pathlib import Path


SRC = Path("services/workflow_logistica_sucursal.py").read_text(encoding="utf-8")


def test_logistica_sucursal_no_hace_commit_ni_mensajes():
    prohibidos = [
        "db.session.commit",
        "ml_enviar",
        "wa_enviar",
        "wa_auto",
        "registrar_envio_automatico",
        "url_for(",
        "render_template",
    ]

    for prohibido in prohibidos:
        assert prohibido not in SRC


def test_logistica_sucursal_expone_contrato():
    assert "def normalizar_sucursal_operativa" in SRC
    assert "def aplicar_sucursal_elegida_al_pedido" in SRC
