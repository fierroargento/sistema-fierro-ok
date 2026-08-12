"""Obligaciones y pagos históricos de costos productivos."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ObligacionCostoProductivo(db.Model):
    __tablename__ = "obligacion_costo_productivo"
    __table_args__ = (
        UniqueConstraint("costo_fijo_id", "periodo", name="uq_obligacion_costo_periodo"),
        CheckConstraint("importe_centavos > 0", name="ck_obligacion_importe_positivo"),
        CheckConstraint("estado IN ('pendiente', 'parcial', 'pagada', 'anulada')", name="ck_obligacion_estado"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    costo_fijo_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_productivo.id"), nullable=False, index=True)
    version_costo_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_version.id"), nullable=False)
    regla_ajuste_id = db.Column(db.Integer, db.ForeignKey("regla_ajuste_ipc_productivo.id"), index=True)
    propuesta_ajuste_id = db.Column(db.Integer, db.ForeignKey("propuesta_ajuste_ipc_productivo.id"), index=True)
    ajuste_pendiente = db.Column(db.Boolean, default=False, nullable=False, index=True)
    periodo = db.Column(db.Date, nullable=False, index=True)
    fecha_vencimiento = db.Column(db.Date, nullable=False, index=True)
    importe_centavos = db.Column(db.BigInteger, nullable=False)
    estado = db.Column(db.String(20), default="pendiente", nullable=False, index=True)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    costo_fijo = db.relationship("CostoFijoProductivo", backref="obligaciones")
    version_costo = db.relationship("CostoFijoVersion")
    regla_ajuste = db.relationship("ReglaAjusteIPCProductivo")
    propuesta_ajuste = db.relationship("PropuestaAjusteIPCProductivo")


class PagoObligacionCostoProductivo(db.Model):
    __tablename__ = "pago_obligacion_costo_productivo"
    __table_args__ = (
        CheckConstraint("importe_centavos > 0", name="ck_pago_obligacion_importe_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    obligacion_id = db.Column(db.Integer, db.ForeignKey("obligacion_costo_productivo.id"), nullable=False, index=True)
    fecha_pago = db.Column(db.Date, nullable=False, index=True)
    importe_centavos = db.Column(db.BigInteger, nullable=False)
    medio_pago = db.Column(db.String(80))
    referencia = db.Column(db.String(160))
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    obligacion = db.relationship("ObligacionCostoProductivo", backref="pagos")
