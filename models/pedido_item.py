"""
Modelo de artículos asociados a pedidos.
"""

from extensions import db


class PedidoItem(db.Model):
    """Artículo y estado de devolución dentro de un pedido."""

    __tablename__ = "pedido_item"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
    )
    sku = db.Column(db.String(50))
    descripcion = db.Column(db.String(200))
    cantidad = db.Column(db.Integer)

    cantidad_devuelta_ok = db.Column(db.Integer)
    cantidad_devuelta_danada = db.Column(db.Integer)
    estado_devolucion_item = db.Column(db.String(50))
    observacion_devolucion_item = db.Column(db.String(300))
