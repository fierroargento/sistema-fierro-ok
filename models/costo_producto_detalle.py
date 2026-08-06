"""
Detalle historico de componentes del costo productivo.
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class CostoProductoDetalle(db.Model):
    """Snapshot de un componente utilizado en una version de costo."""

    __tablename__ = "costo_producto_detalle"

    __table_args__ = (
        UniqueConstraint(
            "costo_producto_version_id",
            "orden",
            name="uq_costo_detalle_version_orden",
        ),
        CheckConstraint(
            "tipo IN ("
            "'insumo', 'mano_obra', "
            "'elaboracion', 'flete_entrada'"
            ")",
            name="ck_costo_detalle_tipo",
        ),
        CheckConstraint(
            "cantidad >= 0",
            name="ck_costo_detalle_cantidad",
        ),
        CheckConstraint(
            "costo_unitario_centavos >= 0",
            name="ck_costo_detalle_unitario",
        ),
        CheckConstraint(
            "porcentaje_merma >= 0 "
            "AND porcentaje_merma <= 100",
            name="ck_costo_detalle_merma",
        ),
        CheckConstraint(
            "subtotal_centavos >= 0",
            name="ck_costo_detalle_subtotal",
        ),
        CheckConstraint(
            "orden >= 0",
            name="ck_costo_detalle_orden",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    costo_producto_version_id = db.Column(
        db.Integer,
        db.ForeignKey("costo_producto_version.id"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )
    codigo = db.Column(db.String(80))
    concepto = db.Column(
        db.String(200),
        nullable=False,
    )
    cantidad = db.Column(
        db.Numeric(18, 6),
        nullable=False,
    )
    unidad_medida = db.Column(
        db.String(30),
        nullable=False,
    )
    costo_unitario_centavos = db.Column(
        db.BigInteger,
        nullable=False,
    )
    porcentaje_merma = db.Column(
        db.Numeric(9, 6),
        default=0,
        nullable=False,
    )
    subtotal_centavos = db.Column(
        db.BigInteger,
        nullable=False,
    )
    observacion = db.Column(db.String(500))
    orden = db.Column(
        db.Integer,
        nullable=False,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        nullable=False,
    )

    version = db.relationship(
        "CostoProductoVersion",
        back_populates="detalles",
    )
