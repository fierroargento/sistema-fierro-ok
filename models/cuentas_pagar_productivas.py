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


class ReglaObligacionCostoProductivo(db.Model):
    """Calendario versionable de generación de obligaciones por concepto."""

    __tablename__ = "regla_obligacion_costo_productivo"
    __table_args__ = (
        UniqueConstraint("costo_fijo_id", name="uq_regla_obligacion_costo"),
        CheckConstraint("frecuencia_meses BETWEEN 1 AND 120", name="ck_regla_obligacion_frecuencia"),
        CheckConstraint("dia_vencimiento BETWEEN 1 AND 31", name="ck_regla_obligacion_dia"),
        CheckConstraint("meses_anticipacion BETWEEN 0 AND 24", name="ck_regla_obligacion_anticipacion"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    costo_fijo_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_productivo.id"), nullable=False, index=True)
    frecuencia_meses = db.Column(db.Integer, default=1, nullable=False)
    periodo_inicio = db.Column(db.Date, nullable=False, index=True)
    dia_vencimiento = db.Column(db.Integer, default=1, nullable=False)
    meses_anticipacion = db.Column(db.Integer, default=2, nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive, nullable=False)

    costo_fijo = db.relationship("CostoFijoProductivo", backref="regla_obligacion")


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
    comprobante = db.Column(db.String(500))
    observacion = db.Column(db.String(500))
    anulado = db.Column(db.Boolean, default=False, nullable=False, index=True)
    motivo_anulacion = db.Column(db.String(500))
    fecha_anulacion = db.Column(db.DateTime)
    anulado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    obligacion = db.relationship("ObligacionCostoProductivo", backref="pagos")
