"""Reglas versionadas de integridad y vigencia para datos comerciales observados."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class ReglaValidacionCanalVersion(db.Model):
    __tablename__ = "regla_validacion_canal_version"
    __table_args__ = (
        UniqueConstraint("lista_precio_id", "numero_version", name="uq_regla_validacion_canal_version"),
        CheckConstraint("vigencia_precio_horas > 0 AND vigencia_cargos_horas > 0 AND vigencia_envio_horas > 0 AND vigencia_promocion_horas > 0", name="ck_regla_validacion_vigencias"),
        CheckConstraint("estado IN ('preparatorio', 'vigente', 'archivado', 'cancelado')", name="ck_regla_validacion_estado"),
        Index("uq_regla_validacion_canal_vigente", "lista_precio_id", unique=True, postgresql_where=text("vigente IS TRUE"), sqlite_where=text("vigente IS TRUE")),
    )
    id = db.Column(db.Integer, primary_key=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    vigencia_precio_horas = db.Column(db.Integer, default=168, nullable=False)
    vigencia_cargos_horas = db.Column(db.Integer, default=168, nullable=False)
    vigencia_envio_horas = db.Column(db.Integer, default=168, nullable=False)
    vigencia_promocion_horas = db.Column(db.Integer, default=168, nullable=False)
    exigir_precio_observado = db.Column(db.Boolean, default=True, nullable=False)
    exigir_cargos_observados = db.Column(db.Boolean, default=True, nullable=False)
    exigir_envio_observado = db.Column(db.Boolean, default=True, nullable=False)
    exigir_promocion_observada = db.Column(db.Boolean, default=False, nullable=False)
    exigir_identidad_unica = db.Column(db.Boolean, default=True, nullable=False)
    estado = db.Column(db.String(20), default="preparatorio", nullable=False, index=True)
    vigente = db.Column(db.Boolean, default=False, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lista_precio = db.relationship("ListaPrecio")
