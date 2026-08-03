"""
Modelo de catálogos comerciales del Grupo Fierro.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class Catalogo(db.Model):
    """
    Catálogo comercial perteneciente a una organización.

    Puede ser general o estar asociado a una unidad de negocio.
    Los catálogos nuevos nacen desactivados.
    """

    __tablename__ = "catalogo"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_catalogo_organizacion_codigo",
        ),
    )

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
    unidad_negocio_id = db.Column(
        db.Integer,
        db.ForeignKey("unidad_negocio.id"),
        nullable=True,
        index=True,
    )
    codigo = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    descripcion = db.Column(db.String(500))
    moneda = db.Column(
        db.String(10),
        default="ARS",
        nullable=False,
    )
    estado = db.Column(
        db.String(20),
        default="desactivado",
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
        backref="catalogos",
    )
    unidad_negocio = db.relationship(
        "UnidadNegocio",
        backref="catalogos",
    )
