"""
Puntos de venta de cada entidad fiscal.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class PuntoVentaFiscal(db.Model):
    """
    Punto de venta independiente por CUIT.

    Los puntos nuevos nacen desactivados y sin emisión real.
    """

    __tablename__ = "punto_venta_fiscal"

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
    entidad_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("entidad_fiscal.id"),
        nullable=False,
        index=True,
    )
    configuracion_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("configuracion_fiscal.id"),
        nullable=False,
        index=True,
    )
    numero = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    estado = db.Column(
        db.String(30),
        default="desactivado",
        nullable=False,
        index=True,
    )
    emision_real_habilitada = db.Column(
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
        backref="puntos_venta_fiscales",
    )
    entidad_fiscal = db.relationship(
        "EntidadFiscal",
        backref="puntos_venta",
    )
    configuracion = db.relationship(
        "ConfiguracionFiscal",
        backref="puntos_venta",
    )
