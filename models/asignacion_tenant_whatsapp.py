"""Propuestas auditables para asignar identidad SaaS a mensajes WhatsApp."""

from sqlalchemy import CheckConstraint, Index
from extensions import db
from services.fechas import ahora_utc_naive


class AsignacionTenantWhatsApp(db.Model):
    __tablename__ = "asignacion_tenant_whatsapp"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('preparada', 'aprobada', 'aplicada', 'rechazada', 'obsoleta')",
            name="ck_asignacion_tenant_whatsapp_estado",
        ),
        Index("ix_asignacion_tenant_whatsapp_bandeja", "organizacion_id", "estado", "fecha_creacion"),
    )
    id = db.Column(db.Integer, primary_key=True)
    mensaje_id = db.Column(db.Integer, db.ForeignKey("whatsapp_mensaje.id"), nullable=False, index=True)
    pedido_id_snapshot = db.Column(db.Integer)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default="preparada", index=True)
    motivo = db.Column(db.String(500))
    creado_por_username = db.Column(db.String(80))
    aprobado_por_username = db.Column(db.String(80))
    aplicado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_aprobacion = db.Column(db.DateTime)
    fecha_aplicacion = db.Column(db.DateTime)
