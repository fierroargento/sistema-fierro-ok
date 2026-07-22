"""
Historial persistido de eventos de tracking externo.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class TrackingEvento(db.Model):
    """Evento de tracking externo asociado a un pedido."""

    __tablename__ = "tracking_evento"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=False,
        index=True,
    )
    empresa = db.Column(db.String(80))
    seguimiento = db.Column(db.String(100))
    estado = db.Column(db.String(300))
    clasificacion = db.Column(db.String(50))
    raw_json = db.Column(db.Text)
    origen = db.Column(db.String(50))
    fecha_evento = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
