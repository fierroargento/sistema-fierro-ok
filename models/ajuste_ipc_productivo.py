"""IPC oficial y propuestas versionadas para costos indirectos productivos."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class IndiceIPCOficial(db.Model):
    __tablename__ = "indice_ipc_oficial"
    __table_args__ = (
        UniqueConstraint("serie", "periodo", name="uq_indice_ipc_serie_periodo"),
        CheckConstraint("valor > 0", name="ck_indice_ipc_valor_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    serie = db.Column(db.String(100), nullable=False, index=True)
    periodo = db.Column(db.Date, nullable=False, index=True)
    valor = db.Column(db.Numeric(20, 8), nullable=False)
    fuente_url = db.Column(db.String(500), nullable=False)
    fecha_consulta = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)


class ReglaAjusteIPCProductivo(db.Model):
    __tablename__ = "regla_ajuste_ipc_productivo"
    __table_args__ = (
        UniqueConstraint("costo_fijo_id", name="uq_regla_ipc_costo_fijo"),
        CheckConstraint("frecuencia_meses > 0", name="ck_regla_ipc_frecuencia"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    costo_fijo_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_productivo.id"), nullable=False, index=True)
    serie = db.Column(db.String(100), nullable=False)
    frecuencia_meses = db.Column(db.Integer, default=6, nullable=False)
    proximo_ajuste = db.Column(db.Date, nullable=False, index=True)
    activa = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    costo_fijo = db.relationship("CostoFijoProductivo", backref="regla_ajuste_ipc", uselist=False)


class PropuestaAjusteIPCProductivo(db.Model):
    __tablename__ = "propuesta_ajuste_ipc_productivo"
    __table_args__ = (
        UniqueConstraint("regla_id", "vigente_desde", name="uq_propuesta_ipc_regla_vigencia"),
        CheckConstraint("estado IN ('pendiente', 'aprobada', 'aplicada', 'descartada')", name="ck_propuesta_ipc_estado"),
    )

    id = db.Column(db.Integer, primary_key=True)
    regla_id = db.Column(db.Integer, db.ForeignKey("regla_ajuste_ipc_productivo.id"), nullable=False, index=True)
    version_origen_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_version.id"), nullable=False)
    periodo_base = db.Column(db.Date, nullable=False)
    periodo_final = db.Column(db.Date, nullable=False)
    indice_base = db.Column(db.Numeric(20, 8), nullable=False)
    indice_final = db.Column(db.Numeric(20, 8), nullable=False)
    variacion_porcentual = db.Column(db.Numeric(14, 6), nullable=False)
    importe_actual_centavos = db.Column(db.BigInteger, nullable=False)
    importe_propuesto_centavos = db.Column(db.BigInteger, nullable=False)
    vigente_desde = db.Column(db.Date, nullable=False, index=True)
    estado = db.Column(db.String(20), default="pendiente", nullable=False, index=True)
    aprobado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_aprobacion = db.Column(db.DateTime)
    fecha_aplicacion = db.Column(db.DateTime)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    regla = db.relationship("ReglaAjusteIPCProductivo", backref="propuestas")
    version_origen = db.relationship("CostoFijoVersion")
