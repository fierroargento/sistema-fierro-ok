"""
Modelo de ventas de Mercado Libre ignoradas operativamente.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class PedidoIgnoradoML(db.Model):
    """
    Venta eliminada manualmente para impedir que el sincronizador
    vuelva a incorporarla al flujo operativo.
    """

    __tablename__ = "pedido_ignorado_ml"

    id = db.Column(db.Integer, primary_key=True)
    id_venta = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    motivo = db.Column(db.String(255))
    pedido_local_id = db.Column(db.Integer)
    usuario = db.Column(db.String(100))
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
