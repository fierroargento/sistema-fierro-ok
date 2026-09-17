"""Politicas versionadas de descuentos operativos por canal."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class ReglaCanalVersion(db.Model):
    __tablename__ = "regla_canal_version"
    __table_args__ = (
        UniqueConstraint("lista_precio_id", "numero_version", name="uq_regla_canal_version"),
        CheckConstraint("comision_pct >= 0 AND comision_pct < 100", name="ck_regla_canal_comision"),
        CheckConstraint("publicidad_pct >= 0 AND publicidad_pct < 100", name="ck_regla_canal_publicidad"),
        CheckConstraint("financiacion_pct >= 0 AND financiacion_pct < 100", name="ck_regla_canal_financiacion"),
        CheckConstraint("devoluciones_pct >= 0 AND devoluciones_pct < 100", name="ck_regla_canal_devoluciones"),
        CheckConstraint("comision_pct + publicidad_pct + financiacion_pct + devoluciones_pct < 100", name="ck_regla_canal_costos_porcentuales"),
        CheckConstraint("umbral_envio_centavos >= 0 AND costo_envio_default_centavos >= 0", name="ck_regla_canal_envio"),
        CheckConstraint("incremento_redondeo_centavos > 0", name="ck_regla_canal_redondeo"),
        CheckConstraint("estado IN ('preparatorio', 'vigente', 'archivado', 'cancelado')", name="ck_regla_canal_estado"),
        Index("uq_regla_canal_vigente", "lista_precio_id", unique=True, postgresql_where=text("vigente IS TRUE"), sqlite_where=text("vigente IS TRUE")),
    )
    id = db.Column(db.Integer, primary_key=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    comision_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    publicidad_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    financiacion_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    devoluciones_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    umbral_envio_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    costo_envio_default_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    incremento_redondeo_centavos = db.Column(db.BigInteger, default=1, nullable=False)
    estado = db.Column(db.String(20), default="preparatorio", nullable=False, index=True)
    vigente = db.Column(db.Boolean, default=False, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lista_precio = db.relationship("ListaPrecio", backref="reglas_canal")
    tramos = db.relationship("ReglaCanalCargoTramo", back_populates="regla", cascade="all, delete-orphan", order_by="ReglaCanalCargoTramo.precio_desde_centavos")


class ReglaCanalCargoTramo(db.Model):
    __tablename__ = "regla_canal_cargo_tramo"
    __table_args__ = (
        UniqueConstraint("regla_canal_version_id", "precio_desde_centavos", name="uq_regla_canal_tramo_desde"),
        CheckConstraint("precio_desde_centavos >= 0 AND cargo_fijo_centavos >= 0", name="ck_regla_canal_tramo_no_negativo"),
        CheckConstraint("precio_hasta_centavos IS NULL OR precio_hasta_centavos > precio_desde_centavos", name="ck_regla_canal_tramo_rango"),
    )
    id = db.Column(db.Integer, primary_key=True)
    regla_canal_version_id = db.Column(db.Integer, db.ForeignKey("regla_canal_version.id"), nullable=False, index=True)
    precio_desde_centavos = db.Column(db.BigInteger, nullable=False)
    precio_hasta_centavos = db.Column(db.BigInteger)
    cargo_fijo_centavos = db.Column(db.BigInteger, nullable=False)
    regla = db.relationship("ReglaCanalVersion", back_populates="tramos")
