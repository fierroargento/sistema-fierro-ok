from pathlib import Path


SRC = Path("services/workflow_correo_sucursal_oferta.py").read_text(encoding="utf-8")


def test_oferta_correo_no_hace_commit_ni_envia_mensajes():
    prohibidos = [
        "db.session.commit",
        "from app import db",
        "ml_enviar",
        "wa_enviar",
        "wa_auto",
        "registrar_envio_automatico",
        "url_for(",
        "render_template",
        "request.",
        "session.",
        "current_user",
    ]

    for prohibido in prohibidos:
        assert prohibido not in SRC


def test_oferta_correo_expone_contrato():
    assert "class OfertaSucursalesCorreo" in SRC
    assert "def preparar_oferta_sucursales_correo" in SRC
    assert "def armar_mensaje_sucursales_correo" in SRC
