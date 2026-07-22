"""
Modelo de agregados manuales asociados a pedidos.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class PedidoAgregadoAPB(db.Model):
    """
    Agrupador de artículos agregados manualmente a un pedido.

    Conserva comprobantes y el snapshot de los artículos agregados.
    """

    __tablename__ = "pedido_agregado_apb"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=False,
        index=True,
    )
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(50))
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
    comprobante_dux_url = db.Column(
        db.String(500),
        nullable=False,
    )
    comprobante_dux_public_id = db.Column(db.String(255))
    comprobante_pago_url = db.Column(
        db.String(500),
        nullable=False,
    )
    comprobante_pago_public_id = db.Column(db.String(255))
    items_json = db.Column(
        db.Text,
        nullable=False,
    )
