"""
Existencias internas por producto y sucursal operativa.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class ExistenciaSucursal(db.Model):
    """
    Stock independiente por producto y sucursal.

    No reemplaza ni modifica el stock de los canales.
    Los controles nuevos nacen desactivados.
    """

    __tablename__ = "existencia_sucursal"

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
    sucursal_operativa_id = db.Column(
        db.Integer,
        db.ForeignKey("sucursal_operativa.id"),
        nullable=False,
        index=True,
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey("producto.id"),
        nullable=False,
        index=True,
    )
    stock_actual = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    stock_reservado = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    stock_minimo = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    stock_maximo = db.Column(
        db.Integer,
        nullable=True,
    )
    control_activo = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )

    organizacion = db.relationship(
        "Organizacion",
        backref="existencias_sucursales",
    )
    sucursal = db.relationship(
        "SucursalOperativa",
        backref="existencias_productos",
    )
    producto = db.relationship(
        "Producto",
        backref="existencias_sucursales",
    )
