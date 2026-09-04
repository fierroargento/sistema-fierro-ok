"""Controles y eventos internos previos a cualquier integracion de canal."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ControlIntegracionCanal(db.Model):
    __tablename__ = "control_integracion_canal"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "unidad_negocio_id", "canal", "cuenta_codigo", name="uq_control_integracion_canal"),
        CheckConstraint("modo IN ('deshabilitado', 'diagnostico', 'simulacion')", name="ck_control_integracion_modo"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    canal = db.Column(db.String(50), nullable=False, index=True)
    cuenta_codigo = db.Column(db.String(100), nullable=False, index=True)
    modo = db.Column(db.String(20), default="deshabilitado", nullable=False)
    recepcion_externa_habilitada = db.Column(db.Boolean, default=False, nullable=False)
    acciones_externas_habilitadas = db.Column(db.Boolean, default=False, nullable=False)
    certificacion_interna_aprobada = db.Column(db.Boolean, default=False, nullable=False)
    certificacion_observacion = db.Column(db.String(500))
    actualizado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    actualizado_por_username = db.Column(db.String(80))
    fecha_actualizacion = db.Column(db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive, nullable=False)


class EventoIntegracionStaging(db.Model):
    __tablename__ = "evento_integracion_staging"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "canal", "cuenta_codigo", "tipo_evento", "referencia_evento", name="uq_evento_integracion_staging"),
        CheckConstraint("origen IN ('manual', 'simulacion')", name="ck_evento_staging_origen"),
        CheckConstraint("estado IN ('recibido', 'validado', 'rechazado', 'aplicado_simulado')", name="ck_evento_staging_estado"),
        Index("ix_evento_staging_bandeja", "organizacion_id", "unidad_negocio_id", "canal", "estado"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    control_id = db.Column(db.Integer, db.ForeignKey("control_integracion_canal.id"), nullable=False, index=True)
    canal = db.Column(db.String(50), nullable=False)
    cuenta_codigo = db.Column(db.String(100), nullable=False)
    tipo_evento = db.Column(db.String(40), nullable=False, index=True)
    referencia_evento = db.Column(db.String(160), nullable=False)
    origen = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(25), default="recibido", nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False, index=True)
    error_validacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_recepcion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_proceso = db.Column(db.DateTime)
    control = db.relationship("ControlIntegracionCanal")
