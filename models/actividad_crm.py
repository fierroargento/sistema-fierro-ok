"""
Actividades, notas y tareas del CRM interno.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class ActividadCRM(db.Model):
    """
    Seguimiento manual de un cliente u oportunidad.

    No envía mensajes ni ejecuta automatizaciones.
    """

    __tablename__ = "actividad_crm"

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
    oportunidad_crm_id = db.Column(
        db.Integer,
        db.ForeignKey("oportunidad_crm.id"),
        nullable=True,
        index=True,
    )
    tipo = db.Column(
        db.String(30),
        default="nota",
        nullable=False,
        index=True,
    )
    asunto = db.Column(
        db.String(200),
        nullable=False,
    )
    detalle = db.Column(db.Text)
    estado = db.Column(
        db.String(30),
        default="pendiente",
        nullable=False,
        index=True,
    )
    fecha_vencimiento = db.Column(
        db.DateTime,
        nullable=True,
    )
    fecha_completada = db.Column(
        db.DateTime,
        nullable=True,
    )
    creado_por = db.Column(db.String(100))
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
        backref="actividades_crm",
    )
    cliente = db.relationship(
        "ClienteCRM",
        backref="actividades",
    )
    oportunidad = db.relationship(
        "OportunidadCRM",
        backref="actividades",
    )
