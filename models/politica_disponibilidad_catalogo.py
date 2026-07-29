"""
Política futura de disponibilidad comercial por sucursal.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class PoliticaDisponibilidadCatalogo(db.Model):
    """
    Relaciona un producto de catálogo con una sucursal.

    No publica stock ni modifica canales externos.
    Las políticas nuevas nacen desactivadas.
    """

    __tablename__ = "politica_disponibilidad_catalogo"

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
    catalogo_producto_id = db.Column(
        db.Integer,
        db.ForeignKey("catalogo_producto.id"),
        nullable=False,
        index=True,
    )
    sucursal_operativa_id = db.Column(
        db.Integer,
        db.ForeignKey("sucursal_operativa.id"),
        nullable=False,
        index=True,
    )
    activa = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    permite_sin_stock = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )
    umbral_publicacion = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    maximo_publicable = db.Column(
        db.Integer,
        nullable=True,
    )
    dias_preparacion = db.Column(
        db.Integer,
        default=0,
        nullable=False,
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
        backref="politicas_disponibilidad",
    )
    catalogo_producto = db.relationship(
        "CatalogoProducto",
        backref="politicas_disponibilidad",
    )
    sucursal = db.relationship(
        "SucursalOperativa",
        backref="politicas_disponibilidad",
    )
