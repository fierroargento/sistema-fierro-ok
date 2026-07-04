from pathlib import Path


SRC = Path("services/workflow_sucursal_decision.py").read_text(encoding="utf-8")


def test_sucursal_decision_no_hace_commit_ni_envia_mensajes():
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


def test_sucursal_decision_expone_contrato_central():
    assert "class DecisionSucursal" in SRC
    assert "def decidir_sucursal_ofrecida" in SRC
    assert "def decidir_sucursal_via_cargo_ofrecida" in SRC
    assert "def decidir_sucursal_correo_ofrecida" in SRC
