from pathlib import Path

from models.whatsapp_mensaje import WhatsAppMensaje


def test_whatsapp_mensaje_expone_modelo_canonico():
    assert (
        WhatsAppMensaje.__tablename__
        == "whatsapp_mensaje"
    )

    columnas = {
        "id",
        "pedido_id",
        "telefono",
        "direccion",
        "autor",
        "texto",
        "message_id_meta",
        "estado",
        "error",
        "fecha",
    }

    assert columnas.issubset(
        set(WhatsAppMensaje.__dict__)
    )


def test_whatsapp_mensaje_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/whatsapp_mensaje.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert 'db.ForeignKey("pedido.id")' in modelo
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class WhatsAppMensaje" not in app
    assert (
        "from models.whatsapp_mensaje import "
        "WhatsAppMensaje"
        in app
    )
