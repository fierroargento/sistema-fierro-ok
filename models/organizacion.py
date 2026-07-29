"""
Modelo raíz de la estructura empresarial interna.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class Organizacion(db.Model):
    """
    Organización propietaria de las unidades de negocio.

    En la instalación actual existe una sola:
    Grupo Fierro.
    """

    __tablename__ = "organizacion"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    slug = db.Column(
        db.String(80),
        unique=True,
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

    unidades_negocio = db.relationship(
        "UnidadNegocio",
        backref="organizacion",
        lazy=True,
    )
