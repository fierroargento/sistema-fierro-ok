"""
Cliente comercial independiente del pedido operativo.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ClienteCRM(db.Model):
    """
    Persona o empresa administrada por el CRM interno.

    No se crea automáticamente desde pedidos o canales.
    Los clientes nuevos nacen desactivados.
    """

    __tablename__ = "cliente_crm"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_cliente_crm_organizacion_codigo",
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
        db.String(200),
        nullable=False,
        index=True,
    )
    tipo = db.Column(
        db.String(30),
        default="persona",
        nullable=False,
        index=True,
    )
    documento = db.Column(
        db.String(30),
        nullable=True,
        index=True,
    )
    email = db.Column(
        db.String(200),
        nullable=True,
        index=True,
    )
    telefono = db.Column(
        db.String(50),
        nullable=True,
        index=True,
    )
    localidad = db.Column(db.String(120))
    provincia = db.Column(db.String(120))
    origen = db.Column(db.String(50))
    observaciones = db.Column(db.Text)
    estado = db.Column(
        db.String(30),
        default="potencial",
        nullable=False,
        index=True,
    )
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
        backref="clientes_crm",
    )
    unidad_negocio = db.relationship(
        "UnidadNegocio",
        backref="clientes_crm",
    )
