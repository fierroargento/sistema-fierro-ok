"""
Auditoría específica del subsistema fiscal.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class EventoFiscal(db.Model):
    """
    Evento interno o respuesta futura del proveedor fiscal.
    """

    __tablename__ = "evento_fiscal"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    borrador_comprobante_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("borrador_comprobante_fiscal.id"),
        nullable=True,
        index=True,
    )
    configuracion_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("configuracion_fiscal.id"),
        nullable=True,
        index=True,
    )
    tipo = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )
    detalle = db.Column(db.Text)
    referencia_externa = db.Column(db.String(150))
    usuario = db.Column(db.String(100))
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        nullable=False,
        index=True,
    )

    borrador = db.relationship(
        "BorradorComprobanteFiscal",
        backref="eventos",
    )
    configuracion = db.relationship(
        "ConfiguracionFiscal",
        backref="eventos",
    )
