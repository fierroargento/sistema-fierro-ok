"""
Historial inmutable de movimientos de inventario.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class MovimientoInventario(db.Model):
    """
    Evidencia de un cambio de stock o reserva.

    No genera movimientos automáticamente desde pedidos.
    """

    __tablename__ = "movimiento_inventario"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=False,
        index=True,
    )
    existencia_sucursal_id = db.Column(
        db.Integer,
        db.ForeignKey("existencia_sucursal.id"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )
    cantidad = db.Column(
        db.Integer,
        nullable=False,
    )
    stock_actual_anterior = db.Column(
        db.Integer,
        nullable=False,
    )
    stock_actual_nuevo = db.Column(
        db.Integer,
        nullable=False,
    )
    stock_reservado_anterior = db.Column(
        db.Integer,
        nullable=False,
    )
    stock_reservado_nuevo = db.Column(
        db.Integer,
        nullable=False,
    )
    motivo = db.Column(
        db.String(300),
        nullable=False,
    )
    referencia = db.Column(db.String(150))
    usuario = db.Column(db.String(100))
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        nullable=False,
        index=True,
    )

    organizacion = db.relationship(
        "Organizacion",
        backref="movimientos_inventario",
    )
    existencia = db.relationship(
        "ExistenciaSucursal",
        backref="movimientos",
    )
