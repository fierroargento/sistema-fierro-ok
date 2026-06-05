from datetime import datetime


def crear_modelo_whatsapp_media_recibida(db):
    """
    Modelo para adjuntos recibidos por WhatsApp.

    SaaS/CRM:
    - empresa_id queda previsto desde el inicio.
    - estado_scan queda previsto para antivirus/control futuro.
    - No reemplaza WhatsAppMensaje: lo complementa.
    """

    class WhatsAppMediaRecibida(db.Model):
        __tablename__ = "whatsapp_media_recibida"

        id = db.Column(db.Integer, primary_key=True)

        empresa_id = db.Column(db.Integer, default=1, index=True)
        pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=True, index=True)

        telefono = db.Column(db.String(30), index=True)
        message_id_meta = db.Column(db.String(120), index=True)
        media_id_meta = db.Column(db.String(120), index=True)

        tipo = db.Column(db.String(30))  # image / document
        mime_type = db.Column(db.String(120))
        filename = db.Column(db.String(255))
        caption = db.Column(db.Text)

        cloudinary_url = db.Column(db.String(500))
        cloudinary_public_id = db.Column(db.String(255))
        size_bytes = db.Column(db.Integer)

        estado_scan = db.Column(db.String(40), default="pendiente", index=True)
        error = db.Column(db.Text)

        fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    return WhatsAppMediaRecibida