"""
Modelo de sucursales y depósitos operativos del Grupo Fierro.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class SucursalOperativa(db.Model):
    """
    Lugar interno desde el que se prepara o despacha un pedido.

    No representa la sucursal del transporte elegida por el cliente.
    Las sucursales nuevas nacen desactivadas.
    """

    __tablename__ = "sucursal_operativa"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_sucursal_operativa_organizacion_codigo",
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

    direccion = db.Column(db.String(250))
    localidad = db.Column(db.String(120))
    provincia = db.Column(db.String(120))
    codigo_postal = db.Column(db.String(20))

    es_principal = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
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
        backref="sucursales_operativas",
    )
