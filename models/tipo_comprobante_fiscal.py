"""
Tipos de comprobante habilitables por punto de venta.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class TipoComprobanteFiscal(db.Model):
    """
    Numeración separada por punto de venta y tipo.

    Crear el registro no permite emitir comprobantes.
    """

    __tablename__ = "tipo_comprobante_fiscal"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    punto_venta_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("punto_venta_fiscal.id"),
        nullable=False,
        index=True,
    )
    codigo_arca = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )
    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    letra = db.Column(
        db.String(5),
        nullable=False,
    )
    ultimo_numero_autorizado = db.Column(
        db.Integer,
        default=0,
        nullable=False,
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

    punto_venta = db.relationship(
        "PuntoVentaFiscal",
        backref="tipos_comprobante",
    )
