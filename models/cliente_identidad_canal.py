"""
Identidades externas de un cliente CRM.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class ClienteIdentidadCanal(db.Model):
    """
    Identificador de un cliente en un canal externo.

    Registrar la identidad no inicia sincronizaciones.
    """

    __tablename__ = "cliente_identidad_canal"

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
    cliente_crm_id = db.Column(
        db.Integer,
        db.ForeignKey("cliente_crm.id"),
        nullable=False,
        index=True,
    )
    canal = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )
    identificador_externo = db.Column(
        db.String(150),
        nullable=False,
        index=True,
    )
    alias = db.Column(db.String(150))
    detalle = db.Column(db.String(500))
    activo = db.Column(
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
        backref="identidades_canal_crm",
    )
    cliente = db.relationship(
        "ClienteCRM",
        backref="identidades_canal",
    )
