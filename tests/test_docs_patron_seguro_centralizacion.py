from pathlib import Path


DOC = Path("docs/auditoria-centralizacion/patron-seguro-centralizacion.md").read_text(encoding="utf-8")


def test_documenta_patron_service_puro_antes_de_app():
    assert "Crear service puro" in DOC
    assert "Conectar app.py con fallback" in DOC
    assert "Validar py_compile de app.py" in DOC


def test_documenta_prohibiciones_de_services_puros():
    assert "db.session.commit" in DOC
    assert "enviar mensajes ML" in DOC
    assert "enviar mensajes WhatsApp" in DOC
    assert "request/session/current_user" in DOC


def test_documenta_patron_usado_en_sucursal_via_cargo():
    assert "workflow_sucursal_decision.py" in DOC
    assert "workflow_logistica_sucursal.py" in DOC
    assert "usar decision central con fallback viejo" in DOC
