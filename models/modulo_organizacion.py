"""
Estado de los módulos opcionales de una organización.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ModuloOrganizacion(db.Model):
    """
    Módulo funcional habilitable de forma independiente.

    Crear o configurar un módulo no lo activa.
    Los módulos nuevos nacen desactivados.
    """

    __tablename__ = "modulo_organizacion"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_modulo_organizacion_codigo",
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
    codigo = db.Column(
        db.String(80),
        nullable=False,
        index=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    estado = db.Column(
        db.String(20),
        default="desactivado",
        nullable=False,
        index=True,
    )
    detalle = db.Column(db.String(500))
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
        backref="modulos",
    )
