"""
Modelo del catálogo operativo de productos.
"""

from extensions import db
from sqlalchemy import UniqueConstraint


class Producto(db.Model):
    """Producto con datos físicos y permisos logísticos."""

    __tablename__ = "producto"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "sku",
            name="uq_producto_organizacion_sku",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=False,
        index=True,
    )
    sku = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )
    descripcion = db.Column(
        db.String(255),
        nullable=False,
        index=True,
    )

    # Catálogo logístico administrado por Admin.
    # No se edita desde los formularios operativos de Carga.
    peso_gr = db.Column(db.Float)
    alto_cm = db.Column(db.Float)
    ancho_cm = db.Column(db.Float)
    largo_cm = db.Column(db.Float)
    permite_correo = db.Column(
        db.Boolean,
        default=True,
    )
    permite_via_cargo = db.Column(
        db.Boolean,
        default=True,
    )
    requiere_revision_logistica = db.Column(
        db.Boolean,
        default=False,
    )
    observacion_logistica = db.Column(db.String(300))

    organizacion = db.relationship(
        "Organizacion",
        backref="productos",
    )
