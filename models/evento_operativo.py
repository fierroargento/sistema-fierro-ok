"""
Registro persistido de eventos operativos y conversacionales.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class EventoOperativo(db.Model):
    """Evento operativo asociado opcionalmente a un pedido."""

    __tablename__ = "evento_operativo"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=True,
        index=True,
    )

    tipo_evento = db.Column(
        db.String(120),
        nullable=False,
        index=True,
    )
    origen = db.Column(db.String(50))
    canal = db.Column(db.String(30))
    owner = db.Column(db.String(30))

    estado_conversacional = db.Column(db.String(80))
    flujo_base = db.Column(db.String(80))

    payload_json = db.Column(db.Text)
    resultado = db.Column(db.String(80))
    detalle = db.Column(db.Text)

    usuario = db.Column(db.String(100))
    procesado = db.Column(
        db.Boolean,
        default=False,
        index=True,
    )

    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
