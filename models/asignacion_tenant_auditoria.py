"""Propuesta auditable para asignar tenant a una auditoría legacy."""
from sqlalchemy import CheckConstraint, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive

class AsignacionTenantAuditoria(db.Model):
    __tablename__ = "asignacion_tenant_auditoria"
    __table_args__ = (UniqueConstraint("auditoria_id", name="uq_asignacion_tenant_auditoria_registro"), CheckConstraint("estado IN ('preparada','aprobada','rechazada','aplicada')", name="ck_asignacion_tenant_auditoria_estado"))
    id = db.Column(db.Integer, primary_key=True)
    auditoria_id = db.Column(db.Integer, db.ForeignKey("auditoria.id"), nullable=False, index=True)
    organizacion_propuesta_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    estado = db.Column(db.String(20), default="preparada", nullable=False, index=True)
    evidencia_json = db.Column(db.Text, nullable=False)
    motivo_rechazo = db.Column(db.String(300))
    preparado_por = db.Column(db.String(100)); aprobado_por = db.Column(db.String(100)); aplicado_por = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive, nullable=False)
    auditoria = db.relationship("Auditoria"); organizacion_propuesta = db.relationship("Organizacion")
