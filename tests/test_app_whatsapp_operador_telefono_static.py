from pathlib import Path


def test_inicio_chat_operador_usa_validacion_central_de_telefono():
    contenido = Path("app.py").read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    assert (
        "from services.telefonos import "
        "es_telefono_whatsapp_argentina_valido_service"
    ) in contenido

    assert (
        "if not es_telefono_whatsapp_argentina_valido_service(tel):"
        in contenido
    )

    assert "if not tel or len(tel) < 12:" not in contenido
