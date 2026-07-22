"""
Modelo de respuestas rápidas de WhatsApp.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class RespuestaRapidaWA(db.Model):
    """Respuesta reutilizable para conversaciones de WhatsApp."""

    __tablename__ = "respuesta_rapida_wa"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, default=1, index=True)

    titulo = db.Column(db.String(120), nullable=False)
    texto = db.Column(db.Text, nullable=False)

    categoria = db.Column(
        db.String(80),
        default="General",
        index=True,
    )
    orden = db.Column(
        db.Integer,
        default=100,
        index=True,
    )
    activa = db.Column(
        db.Boolean,
        default=True,
        index=True,
    )

    imagen_url = db.Column(db.String(500))
    imagen_public_id = db.Column(db.String(255))
    imagen_nombre = db.Column(db.String(255))

    creado_por = db.Column(db.String(100))
    creado_en = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    actualizado_en = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )
