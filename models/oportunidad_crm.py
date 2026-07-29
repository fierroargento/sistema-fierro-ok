"""
Oportunidades comerciales del CRM interno.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class OportunidadCRM(db.Model):
    """
    Posible operación comercial asociada a un cliente.

    Los importes se guardan en centavos.
    Las oportunidades nuevas nacen desactivadas.
    """

    __tablename__ = "oportunidad_crm"

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
    unidad_negocio_id = db.Column(
        db.Integer,
        db.ForeignKey("unidad_negocio.id"),
        nullable=True,
        index=True,
    )
    etapa_crm_id = db.Column(
        db.Integer,
        db.ForeignKey("etapa_crm.id"),
        nullable=True,
        index=True,
    )
    titulo = db.Column(
        db.String(200),
        nullable=False,
    )
    origen = db.Column(db.String(50))
    estado = db.Column(
        db.String(30),
        default="abierta",
        nullable=False,
        index=True,
    )
    importe_estimado_centavos = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    probabilidad = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    fecha_cierre_estimada = db.Column(
        db.DateTime,
        nullable=True,
    )
    responsable = db.Column(db.String(100))
    detalle = db.Column(db.Text)
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
        backref="oportunidades_crm",
    )
    cliente = db.relationship(
        "ClienteCRM",
        backref="oportunidades",
    )
    unidad_negocio = db.relationship(
        "UnidadNegocio",
        backref="oportunidades_crm",
    )
    etapa = db.relationship(
        "EtapaCRM",
        backref="oportunidades",
    )
