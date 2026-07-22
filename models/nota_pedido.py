"""
Modelo de notas internas asociadas a pedidos.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class NotaPedido(db.Model):
    """Nota interna de un pedido, visible para administración y carga."""

    __tablename__ = "nota_pedido"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=False,
    )
    texto = db.Column(
        db.Text,
        nullable=False,
    )
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(50))
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
