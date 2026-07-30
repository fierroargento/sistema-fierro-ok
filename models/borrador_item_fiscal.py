"""
Ítems de un borrador de comprobante fiscal.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class BorradorItemFiscal(db.Model):
    """
    Línea comercial calculada sin autorización fiscal.

    La cantidad se guarda en milésimas y los importes
    monetarios en centavos.
    """

    __tablename__ = "borrador_item_fiscal"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    borrador_comprobante_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("borrador_comprobante_fiscal.id"),
        nullable=False,
        index=True,
    )
    descripcion = db.Column(
        db.String(300),
        nullable=False,
    )
    sku = db.Column(db.String(100))
    cantidad_milesimas = db.Column(
        db.Integer,
        nullable=False,
    )
    precio_unitario_centavos = db.Column(
        db.Integer,
        nullable=False,
    )
    alicuota_iva_basis_points = db.Column(
        db.Integer,
        default=2100,
        nullable=False,
    )
    neto_centavos = db.Column(
        db.Integer,
        nullable=False,
    )
    iva_centavos = db.Column(
        db.Integer,
        nullable=False,
    )
    total_centavos = db.Column(
        db.Integer,
        nullable=False,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )

    borrador = db.relationship(
        "BorradorComprobanteFiscal",
        backref="items",
    )
