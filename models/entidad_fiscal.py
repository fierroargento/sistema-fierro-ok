"""
Modelo de entidades fiscales y CUIT del Grupo Fierro.
"""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class EntidadFiscal(db.Model):
    """
    Razón social o persona fiscal habilitable para facturación.

    Crear el registro no habilita emisión de comprobantes.
    Las entidades nuevas nacen desactivadas.
    """

    __tablename__ = "entidad_fiscal"

    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            "codigo",
            name="uq_entidad_fiscal_organizacion_codigo",
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

    razon_social = db.Column(
        db.String(200),
        nullable=False,
    )
    nombre_fantasia = db.Column(db.String(200))
    cuit = db.Column(
        db.String(20),
        unique=True,
        nullable=True,
        index=True,
    )
    condicion_iva = db.Column(db.String(80))
    domicilio_fiscal = db.Column(db.String(300))
    punto_venta_predeterminado = db.Column(
        db.String(20)
    )

    activa = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    facturacion_habilitada = db.Column(
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
        backref="entidades_fiscales",
    )
