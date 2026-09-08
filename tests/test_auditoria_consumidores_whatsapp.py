from pathlib import Path

from services.auditoria_consumidores_whatsapp import (
    auditar_fuentes_consumidores_whatsapp,
)


def test_auditoria_clasifica_accesos_sin_ejecutarlos():
    resultado = auditar_fuentes_consumidores_whatsapp([
        ("modules/whatsapp/webhook.py", "WhatsAppMensaje.query.filter_by(x=1)"),
        ("services/acceso_tenant_whatsapp.py", "WhatsAppMensaje.query.filter_by(x=1)"),
        ("tests/test_x.py", "WhatsAppMensaje.query"),
    ])
    assert resultado["total"] == 1
    assert resultado["controlados"] == 1
    assert resultado["por_grupo"]["webhook"] == 1
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_panel_publica_inventario_de_solo_lectura():
    consultas = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "auditar_consumidores_whatsapp()" in consultas
    assert '"auditoria_consumidores_whatsapp"' in consultas
    assert "auditoria_consumidores_whatsapp.total" in panel
    assert "no ejecuta" in panel.lower()


def test_auditor_no_importa_aplicacion_ni_escribe():
    texto = Path("services/auditoria_consumidores_whatsapp.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "from app import" not in texto
    assert "db.session" not in texto
    assert "requests." not in texto
