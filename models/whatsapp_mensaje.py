"""
Modelo de historial de mensajes de WhatsApp.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class WhatsAppMensaje(db.Model):
    """Mensaje entrante o saliente asociado a un pedido o teléfono."""

    __tablename__ = "whatsapp_mensaje"

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=True,
        index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer,
        db.ForeignKey("unidad_negocio.id"),
        nullable=True,
        index=True,
    )
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        index=True,
    )
    telefono = db.Column(
        db.String(30),
        index=True,
    )
    direccion = db.Column(db.String(10))
    autor = db.Column(db.String(30))
    texto = db.Column(db.Text)
    message_id_meta = db.Column(
        db.String(120),
        index=True,
    )
    estado = db.Column(db.String(40))
    error = db.Column(db.Text)
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
