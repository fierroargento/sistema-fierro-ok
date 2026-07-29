"""
Etapas configurables del proceso comercial.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class EtapaCRM(db.Model):
    """
    Etapa de una oportunidad comercial.

    Las etapas nuevas nacen desactivadas.
    """

    __tablename__ = "etapa_crm"

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
        unique=True,
        nullable=False,
        index=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    orden = db.Column(
        db.Integer,
        default=0,
        nullable=False,
        index=True,
    )
    color = db.Column(
        db.String(20),
        default="#64748b",
        nullable=False,
    )
    activa = db.Column(
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
        backref="etapas_crm",
    )
