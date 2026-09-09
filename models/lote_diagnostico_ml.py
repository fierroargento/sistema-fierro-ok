"""Historial interno y auditable de diagnosticos comerciales ML."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class LoteDiagnosticoML(db.Model):
    __tablename__ = "lote_diagnostico_ml"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "unidad_negocio_id", "cuenta_codigo", "lote_id",
            name="uq_lote_diagnostico_ml_tenant",
        ),
        CheckConstraint(
            "estado IN ('preparado', 'revision', 'aprobado', 'rechazado', 'obsoleto', 'archivado')",
            name="ck_lote_diagnostico_ml_estado",
        ),
        Index("ix_lote_diagnostico_ml_bandeja", "organizacion_id", "unidad_negocio_id", "estado"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    vinculo_canal_id = db.Column(db.Integer, db.ForeignKey("vinculo_canal_comercial.id"), nullable=False, index=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    cuenta_codigo = db.Column(db.String(120), nullable=False, index=True)
    lote_id = db.Column(db.String(64), nullable=False, index=True)
    huella_dependencias = db.Column(db.String(64), nullable=False, index=True)
    firmas_secciones_json = db.Column(db.Text, nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    resultado_json = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default="preparado", nullable=False, index=True)
    puede_ejecutar = db.Column(db.Boolean, default=False, nullable=False)
    motivo_decision = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    revisado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    revisado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_revision = db.Column(db.DateTime)


class EventoLoteDiagnosticoML(db.Model):
    __tablename__ = "evento_lote_diagnostico_ml"
    __table_args__ = (
        Index("ix_evento_lote_ml_historial", "lote_diagnostico_id", "fecha_evento"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lote_diagnostico_id = db.Column(db.Integer, db.ForeignKey("lote_diagnostico_ml.id"), nullable=False, index=True)
    estado_anterior = db.Column(db.String(20))
    estado_nuevo = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(500))
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    username = db.Column(db.String(80))
    fecha_evento = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lote = db.relationship("LoteDiagnosticoML", backref="eventos")
