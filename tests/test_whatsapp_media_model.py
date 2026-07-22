from pathlib import Path

from models.whatsapp_media import (
    WhatsAppMediaRecibida,
)


def test_modelo_media_conserva_contrato():
    assert WhatsAppMediaRecibida.__tablename__ == (
        "whatsapp_media_recibida"
    )

    for nombre in (
        "id",
        "empresa_id",
        "pedido_id",
        "telefono",
        "message_id_meta",
        "media_id_meta",
        "tipo",
        "mime_type",
        "filename",
        "caption",
        "cloudinary_url",
        "cloudinary_public_id",
        "size_bytes",
        "estado_scan",
        "error",
        "fecha",
    ):
        assert hasattr(
            WhatsAppMediaRecibida,
            nombre,
        )

    fuente = Path(
        "models/whatsapp_media.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "class WhatsAppMediaRecibida(db.Model):"
        in fuente
    )
    assert (
        '__tablename__ = "whatsapp_media_recibida"'
        in fuente
    )
    assert 'db.ForeignKey("pedido.id")' in fuente
    assert 'default="pendiente"' in fuente
    assert "default=ahora_utc_naive" in fuente
    assert (
        "def crear_modelo_whatsapp_media_recibida"
        not in fuente
    )


def test_consumidores_importan_media_canonico():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    webhook = Path(
        "modules/whatsapp/webhook.py"
    ).read_text(encoding="utf-8-sig")

    import_canonico = (
        "from models.whatsapp_media import "
        "WhatsAppMediaRecibida"
    )

    assert import_canonico in app
    assert import_canonico in webhook
    assert (
        "crear_modelo_whatsapp_media_recibida"
        not in app
    )
    assert (
        "from app import WhatsAppMediaRecibida"
        not in webhook
    )
