"""
Borradores fiscales sin emisión externa.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class BorradorComprobanteFiscal(db.Model):
    """
    Comprobante preparado internamente.

    No representa un comprobante autorizado por ARCA.
    No tiene relación automática con Pedido.
    """

    __tablename__ = "borrador_comprobante_fiscal"

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
    entidad_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("entidad_fiscal.id"),
        nullable=False,
        index=True,
    )
    punto_venta_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("punto_venta_fiscal.id"),
        nullable=False,
        index=True,
    )
    tipo_comprobante_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("tipo_comprobante_fiscal.id"),
        nullable=False,
        index=True,
    )
    cliente_crm_id = db.Column(
        db.Integer,
        db.ForeignKey("cliente_crm.id"),
        nullable=True,
        index=True,
    )
    receptor_nombre = db.Column(
        db.String(200),
        nullable=False,
    )
    receptor_documento = db.Column(db.String(30))
    receptor_condicion_iva = db.Column(db.String(80))
    moneda = db.Column(
        db.String(10),
        default="ARS",
        nullable=False,
    )
    estado = db.Column(
        db.String(30),
        default="borrador",
        nullable=False,
        index=True,
    )
    neto_centavos = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    iva_centavos = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    otros_tributos_centavos = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    total_centavos = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )
    cae = db.Column(db.String(30))
    cae_vencimiento = db.Column(db.DateTime)
    numero_autorizado = db.Column(db.Integer)
    referencia_externa = db.Column(db.String(150))
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
        backref="borradores_fiscales",
    )
    entidad_fiscal = db.relationship(
        "EntidadFiscal",
        backref="borradores_fiscales",
    )
    punto_venta = db.relationship(
        "PuntoVentaFiscal",
        backref="borradores",
    )
    tipo_comprobante = db.relationship(
        "TipoComprobanteFiscal",
        backref="borradores",
    )
    cliente_crm = db.relationship(
        "ClienteCRM",
        backref="borradores_fiscales",
    )
