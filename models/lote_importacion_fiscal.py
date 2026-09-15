"""Lote auditable de borradores fiscales importados sin emisión externa."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive


class LoteImportacionFiscal(db.Model):
    __tablename__ = "lote_importacion_fiscal"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "huella_documento", name="uq_lote_importacion_fiscal_huella"),
        CheckConstraint("estado IN ('confirmado','anulado')", name="ck_lote_importacion_fiscal_estado"),
        CheckConstraint("emision_real = false", name="ck_lote_importacion_fiscal_sin_emision"),
        Index("ix_lote_importacion_fiscal_historial", "organizacion_id", "fecha_creacion"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    huella_documento = db.Column(db.String(64), nullable=False, index=True)
    huella_plan = db.Column(db.String(64), nullable=False)
    estado = db.Column(db.String(20), default="confirmado", nullable=False, index=True)
    comprobantes_creados = db.Column(db.Integer, nullable=False)
    items_creados = db.Column(db.Integer, nullable=False)
    rechazados = db.Column(db.Integer, default=0, nullable=False)
    evidencia_json = db.Column(db.Text, nullable=False)
    emision_real = db.Column(db.Boolean, default=False, nullable=False)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True, index=True)
    creado_por_username = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
