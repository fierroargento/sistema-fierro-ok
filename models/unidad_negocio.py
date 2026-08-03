"""
Modelo de unidades de negocio y marcas del Grupo Fierro.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class UnidadNegocio(db.Model):
    """
    Marca o división comercial perteneciente a una organización.

    Ejemplos actuales:
    - Fierro 100% Argento
    - Náutica del Plata
    """

    __tablename__ = "unidad_negocio"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_unidad_negocio_organizacion_codigo",
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
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    codigo = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )
    activa = db.Column(
        db.Boolean,
        default=True,
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
